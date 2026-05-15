import socket
import threading
import os
import uuid
import datetime
import numpy as np
import platform
import subprocess
from tkinter import *
from tkinter import filedialog, ttk, messagebox, colorchooser
from PIL import Image, ImageTk
import cv2
import sounddevice as sd
from scipy.io.wavfile import read as wav_read, write as wav_write

root = Tk()
root.withdraw()
root.geometry("500x750")
root.configure(bg="#EFEAE2")

client_name = ""
reply_context = ""
my_messages_db = {}
chat_images = []
pending_media_path = None
pending_media_type = None

WA_GREEN = "#00A884"
WA_BG = "#EFEAE2"
WA_BUBBLE_ME = "#D9FDD3"
WA_BUBBLE_FRIEND = "#FFFFFF"

BOTTOM_BAR_BG = "#F0F2F5"
INPUT_FIELD_BG = "#DCE1E5" 
WA_TEXT_DARK = "#111B21"
WA_TEXT_LIGHT = "#667781"

# converts seconds into mm:ss format so it looks nice
def format_duration(seconds):
    try:
        s = int(float(seconds))
        m, s = divmod(s, 60)
        return f"{m:02d}:{s:02d}"
    except:
        return ""

# handles the login screen and sets up the user's download folder
def submit_login(event=None):
    global client_name, user_dir
    client_name = entry_name.get().strip()
    if not client_name:
        client_name = f"User_{str(uuid.uuid4())[:4]}"
    
    user_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"downloads_{client_name}")
    os.makedirs(user_dir, exist_ok=True)
    
    login_win.destroy()
    root.title(f"{client_name} - WhatsApp")
    root.deiconify()

login_win = Toplevel(root)
login_win.title("Login")
login_win.geometry("300x180")
login_win.configure(bg="#FFFFFF")
login_win.resizable(False, False)
login_win.protocol("WM_DELETE_WINDOW", lambda: root.destroy())

Label(login_win, text="Welcome to WhatsApp", bg="#FFFFFF", fg=WA_GREEN, font=("Segoe UI", 14, "bold")).pack(pady=20)
Label(login_win, text="Enter your name to start chatting:", bg="#FFFFFF", fg=WA_TEXT_DARK, font=("Segoe UI", 9)).pack()
entry_name = Entry(login_win, font=("Segoe UI", 11), justify="center", bd=1, relief=SOLID)
entry_name.pack(pady=10, ipady=5, padx=30, fill=X)
entry_name.bind("<Return>", submit_login)
entry_name.focus()
Button(login_win, text="AGREE AND CONTINUE", command=submit_login, bg=WA_GREEN, fg="white", font=("Segoe UI", 9, "bold"), relief=FLAT, padx=20, pady=5, cursor="hand2").pack(pady=10)

root.wait_window(login_win)

try:
    if not root.winfo_exists(): exit(0)
except: exit(0)

client_id = str(uuid.uuid4())
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    # Changed to localhost and 65432 to match the server code
    sock.connect(('127.0.0.1', 65432))
except:
    messagebox.showerror("Error", "Server is not running!")
    exit(0)

send_lock = threading.Lock()
is_recording = False
is_paused = False
audio_frames = []
fs = 44100
audio_stream = None
pulse_running = False
dot_state = 0

style = ttk.Style()
style.theme_use('clam')
style.configure("TProgressbar", thickness=3, background=WA_GREEN, troughcolor=BOTTOM_BAR_BG, bordercolor=BOTTOM_BAR_BG, lightcolor=WA_GREEN, darkcolor=WA_GREEN)

# applies a solid background color to the whole chat window
def apply_bg_color(color):
    global WA_BG
    WA_BG = color
    root.configure(bg=color)
    chat_container.configure(bg=color)
    chat_canvas.configure(bg=color)
    chat_inner_frame.configure(bg=color)

# opens a color picker so the user can choose a chat background
def choose_bg_color():
    color_code = colorchooser.askcolor(title="Choose background color")[1]
    if color_code: apply_bg_color(color_code)

# shows the popup menu for theme options when clicking the palette icon
def show_theme_menu(event):
    menu = Menu(root, tearoff=0, font=("Segoe UI", 10))
    menu.add_command(label="🎨 Change Background Color", command=choose_bg_color)
    menu.tk_popup(event.x_root, event.y_root)

header_frame = Frame(root, bg=WA_GREEN, height=55)
header_frame.pack(fill=X, side=TOP)
header_frame.pack_propagate(False)

lbl_header_name = Label(header_frame, text=client_name, bg=WA_GREEN, fg="white", font=("Segoe UI", 12, "bold"))
lbl_header_name.pack(side=LEFT, padx=15)

btn_theme = Button(header_frame, text="🎨", bg=WA_GREEN, fg="white", bd=0, relief=FLAT, font=("Segoe UI", 16), cursor="hand2")
btn_theme.pack(side=RIGHT, padx=15)
btn_theme.bind("<Button-1>", show_theme_menu)

# tries to open a file using the default app on Windows, Mac, or Linux
def open_file_in_os(path):
    try:
        if platform.system() == 'Windows': os.startfile(path)
        elif platform.system() == 'Darwin': subprocess.call(('open', path))
        else: subprocess.call(('xdg-open', path))
    except: pass

# grabs the first frame of a video to show it as a thumbnail
def get_video_thumb(video_path):
    cap = cv2.VideoCapture(video_path)
    ret, frame = cap.read()
    cap.release()
    if ret:
        cv2image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(cv2image)
        return img
    return None

# figures out how long a video is in seconds
def get_video_duration(video_path):
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    cap.release()
    if fps > 0: return frames / fps
    return 0.0

# pops up a little window showing when a message was sent, delivered, and read
def show_msg_info(msg_id):
    if msg_id not in my_messages_db: return
    info = my_messages_db[msg_id]
    info_win = Toplevel(root)
    info_win.title("Message Info")
    info_win.geometry("300x200")
    info_win.configure(bg="#FFFFFF")
    Label(info_win, text="Message Info", bg="#FFFFFF", fg=WA_TEXT_DARK, font=("Segoe UI", 12, "bold")).pack(pady=10)
    Frame(info_win, bg="#EFEFEF", height=1).pack(fill=X, padx=20, pady=5)
    Label(info_win, text=f"Sent 🕒: {info.get('sent_time', 'Unknown')}", bg="#FFFFFF", fg=WA_TEXT_DARK, font=("Segoe UI", 10)).pack(anchor="w", padx=30, pady=5)
    Label(info_win, text=f"Delivered ✓✓: {info.get('delivered_time', 'Pending')}", bg="#FFFFFF", fg=WA_TEXT_DARK, font=("Segoe UI", 10)).pack(anchor="w", padx=30, pady=5)
    Label(info_win, text=f"Read (Blue): {info.get('read_time', 'Pending')}", bg="#FFFFFF", fg=WA_TEXT_DARK, font=("Segoe UI", 10)).pack(anchor="w", padx=30, pady=5)

# right-click menu for messages (copy, reply, delete, info)
def show_msg_menu(event, bubble, msg_type, content, sender_name, msg_id):
    menu = Menu(root, tearoff=0, font=("Segoe UI", 9))
    if msg_type == "TEXT": menu.add_command(label="Copy", command=lambda: copy_text(content))
    menu.add_command(label="Reply", command=lambda: setup_reply(msg_type, content, sender_name))
    if sender_name == client_name and msg_id in my_messages_db:
        menu.add_separator()
        menu.add_command(label="Message Info ℹ️", command=lambda: show_msg_info(msg_id))
    menu.add_separator()
    menu.add_command(label="Delete", command=bubble.destroy)
    menu.tk_popup(event.x_root, event.y_root)

# copies the message text to the clipboard
def copy_text(text):
    root.clipboard_clear()
    root.clipboard_append(text)

# sets up the little reply box above the text input
def setup_reply(msg_type, content, sender):
    global reply_context
    snippet = content if msg_type == "TEXT" else f"[{msg_type.lower()}]"
    snippet = snippet[:40] + "..." if len(snippet) > 40 else snippet
    reply_context = f"{sender}: {snippet}"
    reply_lbl.config(text=reply_context)
    reply_frame.pack(before=input_area, fill=X, side=BOTTOM, padx=10, pady=(0,5))
    entry_msg.focus()

# hides the reply box if the user changes their mind
def cancel_reply():
    global reply_context
    reply_context = ""
    reply_frame.pack_forget()

# creates the actual message bubble on the screen (text, image, audio, etc.)
def add_bubble(content_type, content, sender_type, timestamp, filename="", extra=""):
    parts = extra.split('|')
    sender_name = parts[0] if parts else "Unknown"
    reply_ctx = parts[1] if len(parts) > 1 and content_type == "TEXT" else ""
    dur = parts[1] if len(parts) > 1 and content_type in ["AUDIO", "VIDEO"] else "unknown"
    msg_id = parts[2] if len(parts) > 2 else str(uuid.uuid4())

    is_me = sender_type == "me"
    bg_color = WA_BUBBLE_ME if is_me else WA_BUBBLE_FRIEND
    align = E if is_me else W
    
    bubble = Frame(chat_inner_frame, bg=bg_color, padx=8, pady=5)
    bubble.pack(anchor=align, padx=15, pady=4)

    def bind_clickable(widget, path=None):
        widget.bind("<Button-3>", lambda e: show_msg_menu(e, bubble, content_type, content, sender_name, msg_id))
        if path:
            widget.bind("<Button-1>", lambda e: open_file_in_os(path))
            widget.config(cursor="hand2")

    bind_clickable(bubble)

    if reply_ctx:
        rep_color = "#CBE2C8" if is_me else "#F0F0F0"
        rep_frame = Frame(bubble, bg=rep_color, padx=5, pady=3)
        rep_frame.pack(anchor=W, fill=X, pady=(0, 5))
        Label(rep_frame, text=reply_ctx, bg=rep_color, fg=WA_TEXT_LIGHT, font=("Segoe UI", 8, "italic"), justify=LEFT, anchor=W).pack(anchor=W, fill=X)
        bind_clickable(rep_frame)

    if not is_me and content_type != "TEXT":
        Label(bubble, text=sender_name, bg=bg_color, fg=WA_GREEN, font=("Segoe UI", 9, "bold")).pack(anchor=W)

    if content_type == "TEXT":
        lbl = Label(bubble, text=content, bg=bg_color, fg=WA_TEXT_DARK, font=("Segoe UI", 10), wraplength=280, justify=LEFT, anchor=W)
        lbl.pack(anchor=W)
        bind_clickable(lbl)
        
    elif content_type in ["IMAGE", "VIDEO"]:
        try:
            if content_type == "VIDEO":
                img = get_video_thumb(content)
                if not img: img = Image.new('RGB', (150, 150), color='#CCCCCC')
            else:
                img = Image.open(content)
            
            img.thumbnail((250, 250))
            photo = ImageTk.PhotoImage(img)
            chat_images.append(photo)
            
            lbl_img = Label(bubble, image=photo, bg=bg_color)
            lbl_img.pack(anchor=W)
            bind_clickable(lbl_img, content)
            
            if content_type == "VIDEO":
                dur_formatted = format_duration(dur) if dur != "unknown" else ""
                vid_info = Frame(bubble, bg=bg_color)
                vid_info.pack(anchor=W, fill=X, pady=(2,0))
                Label(vid_info, text=f"🎥 {filename}", bg=bg_color, font=("Segoe UI", 8), fg=WA_TEXT_LIGHT, justify=LEFT).pack(side=LEFT)
                if dur_formatted:
                    Label(vid_info, text=dur_formatted, bg=bg_color, font=("Segoe UI", 8), fg=WA_TEXT_LIGHT).pack(side=RIGHT)
                bind_clickable(vid_info, content)
            else:
                 Label(bubble, text=f"📷 {filename}", bg=bg_color, font=("Segoe UI", 8), fg=WA_TEXT_LIGHT, justify=LEFT).pack(anchor=W, pady=(2,0))
        except:
            Label(bubble, text="⚠️ Error loading media", bg=bg_color, fg="red", font=("Segoe UI", 9)).pack(anchor=W)

    elif content_type == "AUDIO":
        audio_frame = Frame(bubble, bg=bg_color)
        audio_frame.pack(anchor=W, pady=2)
        bind_clickable(audio_frame)

        play_btn = Button(audio_frame, text="▶", bg=bg_color, fg=WA_TEXT_LIGHT, font=("Consolas", 16), bd=0, relief=FLAT, activebackground=bg_color, cursor="hand2")
        play_btn.pack(side=LEFT, padx=(0, 5))

        dur_formatted = format_duration(dur)
        Label(audio_frame, text=f"🎤 {dur_formatted}", bg=bg_color, font=("Segoe UI", 10), fg=WA_TEXT_DARK).pack(side=LEFT)
        Label(bubble, text=filename, bg=bg_color, font=("Segoe UI", 8), fg=WA_TEXT_LIGHT, justify=LEFT).pack(anchor=W)

        def toggle_play():
            if play_btn['text'] == "▶":
                sd.stop()
                try:
                    fs_r, data = wav_read(content)
                    sd.play(data, fs_r)
                    play_btn.config(text="⏹")
                    def wait_and_reset():
                        sd.wait()
                        if play_btn.winfo_exists(): play_btn.config(text="▶")
                    threading.Thread(target=wait_and_reset, daemon=True).start()
                except: play_btn.config(text="❌")
            else:
                sd.stop()
                play_btn.config(text="▶")
        play_btn.config(command=toggle_play)

    elif content_type == "FILE":
        ext = os.path.splitext(filename)[1].lower()
        if ext == '.pdf': f_icon, f_color = "📕", "#E5252A"
        elif ext in ['.doc', '.docx']: f_icon, f_color = "📘", "#1B5EBE"
        elif ext in ['.xls', '.xlsx']: f_icon, f_color = "📗", "#107C41"
        elif ext in ['.ppt', '.pptx']: f_icon, f_color = "📙", "#D35230"
        else: f_icon, f_color = "📄", WA_TEXT_LIGHT

        f_frame = Frame(bubble, bg=bg_color)
        f_frame.pack(anchor=W, pady=2)
        bind_clickable(f_frame, content)

        Label(f_frame, text=f_icon, bg=bg_color, fg=f_color, font=("Segoe UI", 20)).pack(side=LEFT, padx=(0, 8))
        f_txt = Frame(f_frame, bg=bg_color)
        f_txt.pack(side=LEFT)
        Label(f_txt, text=filename, bg=bg_color, fg=WA_TEXT_DARK, font=("Segoe UI", 9, "bold"), wraplength=200, justify=LEFT, anchor=W).pack(anchor=W)
        Label(f_txt, text=ext[1:].upper() if ext else "FILE", bg=bg_color, fg=f_color, font=("Segoe UI", 8)).pack(anchor=W)

    meta_frame = Frame(bubble, bg=bg_color)
    meta_frame.pack(anchor=E, pady=(2, 0))
    bind_clickable(meta_frame)

    Label(meta_frame, text=timestamp, bg=bg_color, fg=WA_TEXT_LIGHT, font=("Segoe UI", 7)).pack(side=LEFT)

    if is_me:
        tick_lbl = Label(meta_frame, text="✓", bg=bg_color, fg="#8696A0", font=("Consolas", 8))
        tick_lbl.pack(side=LEFT, padx=(3, 0))
        my_messages_db[msg_id] = {'tick_label': tick_lbl, 'sent_time': datetime.datetime.now().strftime("%H:%M:%S")}

        def simulate_delivery():
            if msg_id in my_messages_db and my_messages_db[msg_id]['tick_label'].winfo_exists():
                my_messages_db[msg_id]['tick_label'].config(text="✓✓")
                my_messages_db[msg_id]['delivered_time'] = datetime.datetime.now().strftime("%H:%M:%S")
        def simulate_read():
            if msg_id in my_messages_db and my_messages_db[msg_id]['tick_label'].winfo_exists():
                my_messages_db[msg_id]['tick_label'].config(fg="#53BDEB")
                my_messages_db[msg_id]['read_time'] = datetime.datetime.now().strftime("%H:%M:%S")
                
        root.after(2000, simulate_delivery)
        root.after(4000, simulate_read)

    chat_canvas.update_idletasks()
    chat_canvas.yview_moveto(1.0)

# takes the raw network data from the server and figures out what to do with it
def process_packet(packet):
    try:
        parts = packet.split(b"|||", 3)
        msg_type = parts[0].decode('utf-8')

        if msg_type == "STATUS":
            status_data = parts[3].decode('utf-8').split('|')
            msg_id, status = status_data[0], status_data[1]
            if msg_id in my_messages_db and my_messages_db[msg_id]['tick_label'].winfo_exists():
                if status == "DELIVERED":
                    my_messages_db[msg_id]['tick_label'].config(text="✓✓")
                    my_messages_db[msg_id]['delivered_time'] = datetime.datetime.now().strftime("%H:%M:%S")
                elif status == "READ":
                    my_messages_db[msg_id]['tick_label'].config(fg="#53BDEB")
                    my_messages_db[msg_id]['read_time'] = datetime.datetime.now().strftime("%H:%M:%S")
            return
        
        if len(parts) < 4: return
        meta = parts[2].decode('utf-8').split('|')
        filename = meta[0]
        timestamp = meta[1] if len(meta) > 1 else datetime.datetime.now().strftime("%H:%M")
        duration = meta[2] if len(meta) > 2 else ""
        sender_name = meta[3] if len(meta) > 3 else "Unknown"
        reply_ctx = meta[4] if len(meta) > 4 else ""
        msg_id = meta[5] if len(meta) > 5 else str(uuid.uuid4())
        payload = parts[3]

        try:
            ack_packet = b"STATUS|||" + client_id.encode() + b"|||none|||" + f"{msg_id}|READ".encode() + b"<EOF_MARKER>"
            sock.sendall(ack_packet)
        except: pass

        if msg_type == "TEXT":
            root.after(0, add_bubble, "TEXT", payload.decode('utf-8'), "friend", timestamp, extra=f"{sender_name}|{reply_ctx}|{msg_id}")
        else:
            save_path = os.path.join(user_dir, f"recv_{filename}")
            with open(save_path, "wb") as f: f.write(payload)
            extra_info = f"{sender_name}|{duration}|{msg_id}"
            ext = os.path.splitext(filename)[1].lower()
            if msg_type == "IMAGE": root.after(0, add_bubble, "IMAGE", save_path, "friend", timestamp, filename, extra=extra_info)
            elif msg_type == "AUDIO": root.after(0, add_bubble, "AUDIO", save_path, "friend", timestamp, filename, extra=extra_info)
            elif ext in ['.mp4', '.avi', '.mov', '.mkv'] or msg_type == "VIDEO": root.after(0, add_bubble, "VIDEO", save_path, "friend", timestamp, filename, extra=extra_info)
            else: root.after(0, add_bubble, "FILE", save_path, "friend", timestamp, filename, extra=extra_info)
    except: pass

# grabs the text from the input box and sends it to the server
def send_text(event=None):
    global reply_context
    text = entry_msg.get().strip()
    if text:
        now = datetime.datetime.now().strftime("%H:%M")
        msg_id = str(uuid.uuid4())
        add_bubble("TEXT", text, "me", now, extra=f"{client_name}|{reply_context}|{msg_id}")
        entry_msg.delete(0, END)
        packet = b"TEXT|||" + client_id.encode('utf-8') + b"|||" + f"none|{now}||{client_name}|{reply_context}|{msg_id}".encode('utf-8') + b"|||" + text.encode('utf-8') + b"<EOF_MARKER>"
        try:
            with send_lock: sock.sendall(packet)
        except: messagebox.showerror("Error", "Disconnected from server")
        cancel_reply()

# runs in the background to upload files without freezing the app
def send_media_thread(path, msg_type, is_hd=True, duration="", msg_id=None):
    if msg_id is None: msg_id = str(uuid.uuid4())
    filename = os.path.basename(path)
    now = datetime.datetime.now().strftime("%H:%M")
    ext = os.path.splitext(filename)[1].lower()

    display_type = "FILE"
    if msg_type == b"IMAGE": display_type = "IMAGE"
    elif msg_type == b"AUDIO": display_type = "AUDIO"
    elif ext in ['.mp4', '.avi', '.mov', '.mkv']:
        display_type = "VIDEO"
        if not duration: duration = str(get_video_duration(path))

    if not is_hd and display_type == "IMAGE":
        try:
            img = Image.open(path).convert("RGB")
            temp_path = os.path.join(user_dir, f"compressed_{uuid.uuid4().hex[:6]}.jpg")
            img.save(temp_path, quality=30, optimize=True)
            path = temp_path
            filename = os.path.basename(path)
        except: pass

    root.after(0, add_bubble, display_type, path, "me", now, filename, f"{client_name}|{duration}|{msg_id}")
    root.after(0, lambda: progress_bar.pack(fill=X, before=bottom_panel))

    try:
        with send_lock:
            header = msg_type + b"|||" + client_id.encode('utf-8') + b"|||" + f"{filename}|{now}|{duration}|{client_name}||{msg_id}".encode('utf-8') + b"|||"
            sock.sendall(header)
            total_size = os.path.getsize(path)
            sent = 0
            with open(path, "rb") as f:
                while True:
                    chunk = f.read(65536)
                    if not chunk: break
                    sock.sendall(chunk)
                    sent += len(chunk)
                    progress_bar['value'] = (sent / total_size) * 100
                    root.update_idletasks()
            sock.sendall(b"<EOF_MARKER>")
        progress_bar['value'] = 0
        root.after(0, progress_bar.pack_forget)
    except:
        progress_bar['value'] = 0
        root.after(0, progress_bar.pack_forget)

# triggers the actual sending of a file after the user clicks 'Send' in the preview
def confirm_send_media():
    global pending_media_path, pending_media_type
    if pending_media_path:
        is_hd = hd_var.get()
        threading.Thread(target=send_media_thread, args=(pending_media_path, pending_media_type, is_hd), daemon=True).start()
    cancel_media_preview()

# cancels sending a file and hides the preview box
def cancel_media_preview():
    global pending_media_path, pending_media_type
    pending_media_path = None
    pending_media_type = None
    media_preview_frame.pack_forget()

# shows a little preview bar before sending a file or photo
def setup_media_preview(path, msg_type):
    global pending_media_path, pending_media_type
    pending_media_path = path
    pending_media_type = msg_type
    preview_lbl.config(text=f"📁 {os.path.basename(path)}")
    if msg_type == b"IMAGE": hd_check.pack(side=LEFT, padx=10)
    else: hd_check.pack_forget()
    media_preview_frame.pack(before=input_area, fill=X, side=BOTTOM, padx=10, pady=(0,5))

# opens a file dialog so the user can pick something to send
def select_file():
    path = filedialog.askopenfilename()
    if path:
        ext = os.path.splitext(path)[1].lower()
        if ext in ['.jpg', '.jpeg', '.png']: m_type = b"IMAGE"
        elif ext in ['.mp4', '.avi', '.mov', '.mkv']: m_type = b"VIDEO"
        else: m_type = b"FILE"
        setup_media_preview(path, m_type)

# opens the webcam so the user can snap a quick photo to send
def capture_camera_preview():
    cap = cv2.VideoCapture(0)
    while True:
        ret, frame = cap.read()
        if not ret: break
        cv2.imshow("Camera - Press 'S' to take photo, 'Q' to exit", frame)
        key = cv2.waitKey(1)
        if key == ord('s') or key == ord('S'):
            path = os.path.join(user_dir, f"cam_{uuid.uuid4().hex[:6]}.jpg")
            cv2.imwrite(path, frame)
            setup_media_preview(path, b"IMAGE")
            break
        if key == ord('q') or key == ord('Q'): break
    cap.release()
    cv2.destroyAllWindows()

# shows the paperclip menu for attaching files or taking photos
def show_attach_menu(event):
    menu = Menu(root, tearoff=0, font=("Segoe UI", 11))
    menu.add_command(label="📁 Document / Media", command=select_file)
    menu.add_command(label="📷 Camera", command=capture_camera_preview)
    x = event.widget.winfo_rootx()
    y = event.widget.winfo_rooty() - 55
    menu.tk_popup(x, y)

# animates the "..." while recording voice notes
def update_dots():
    global dot_state, pulse_running
    if not pulse_running:
        rec_status_lbl.config(text="")
        return
    if is_paused:
        rec_status_lbl.config(text="Paused", fg=WA_TEXT_LIGHT)
        return
    dots = [".  ", ".. ", "..."]
    rec_status_lbl.config(text=f"Recording{dots[dot_state]}", fg="#EA4335")
    dot_state = (dot_state + 1) % 3
    root.after(400, update_dots)

# catches the audio chunks from the microphone while recording
def audio_callback(indata, frames, time_info, status):
    if is_recording and not is_paused: audio_frames.append(indata.copy())

# starts or pauses the voice note recording
def record_audio_toggle():
    global is_recording, is_paused, audio_stream, pulse_running, audio_frames
    if not is_recording:
        is_recording = True
        is_paused = False
        audio_frames = []
        audio_stream = sd.InputStream(samplerate=fs, channels=1, callback=audio_callback)
        audio_stream.start()
        mic_btn.config(text="⏸", fg="#EA4335")
        input_area.pack_forget()
        rec_area.pack(fill=X, side=BOTTOM)
        pulse_running = True
        update_dots()
    else:
        if not is_paused:
            is_paused = True
            mic_btn.config(text="▶", fg=WA_GREEN)
        else:
            is_paused = False
            mic_btn.config(text="⏸", fg="#EA4335")
            update_dots()

# saves the recorded voice note and sends it off
def send_audio():
    global is_recording, audio_stream, audio_frames
    if audio_stream:
        audio_stream.stop()
        audio_stream.close()
        audio_stream = None
    if len(audio_frames) > 0:
        audio_data = np.concatenate(audio_frames, axis=0)
        duration = len(audio_data) / fs
        path = os.path.join(user_dir, f"audio_{uuid.uuid4().hex[:6]}.wav")
        wav_write(path, fs, audio_data)
        threading.Thread(target=send_media_thread, args=(path, b"AUDIO", True, str(duration)), daemon=True).start()
    reset_audio_ui()

# trashes the current voice recording and resets the mic button
def delete_audio():
    global audio_frames, audio_stream
    if audio_stream:
        audio_stream.stop()
        audio_stream.close()
        audio_stream = None
    audio_frames = []
    reset_audio_ui()

# puts the bottom bar back to normal after recording
def reset_audio_ui():
    global is_recording, is_paused, pulse_running
    is_recording = False
    is_paused = False
    pulse_running = False
    mic_btn.config(text="🎤", fg=WA_TEXT_LIGHT)
    rec_area.pack_forget()
    input_area.pack(fill=X, side=BOTTOM)

chat_container = Frame(root, bg=WA_BG)
chat_container.pack(fill=BOTH, expand=True)

chat_canvas = Canvas(chat_container, bg=WA_BG, highlightthickness=0)
scrollbar = ttk.Scrollbar(chat_container, orient=VERTICAL, command=chat_canvas.yview)
chat_canvas.configure(yscrollcommand=scrollbar.set)

chat_inner_frame = Frame(chat_canvas, bg=WA_BG)

# makes scrolling work in the chat canvas
def _on_mousewheel(event):
    chat_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
chat_canvas.bind_all("<MouseWheel>", _on_mousewheel)
root.bind_all("<Button-4>", lambda e: chat_canvas.yview_scroll(-1, "units"))
root.bind_all("<Button-5>", lambda e: chat_canvas.yview_scroll(1, "units"))

# updates the scrollable area when messages are added
def on_frame_configure(event):
    chat_canvas.configure(scrollregion=chat_canvas.bbox("all"))

# makes sure the chat frame stretches to fit the window width
def on_canvas_configure(event):
    chat_canvas.itemconfig(canvas_win, width=event.width)

chat_inner_frame.bind("<Configure>", on_frame_configure)
canvas_win = chat_canvas.create_window((0, 0), window=chat_inner_frame, anchor="nw")
chat_canvas.bind('<Configure>', on_canvas_configure)

scrollbar.pack(side=RIGHT, fill=Y)
chat_canvas.pack(side=LEFT, fill=BOTH, expand=True)

progress_bar = ttk.Progressbar(root, orient=HORIZONTAL, length=100, mode='determinate', style="TProgressbar")

bottom_panel = Frame(root, bg=BOTTOM_BAR_BG)
bottom_panel.pack(fill=X, side=BOTTOM)

input_area = Frame(bottom_panel, bg=BOTTOM_BAR_BG, padx=10, pady=8)
input_area.pack(fill=X, side=BOTTOM)

attach_btn = Button(input_area, text="📎", font=("Segoe UI", 14), bg=BOTTOM_BAR_BG, fg=WA_TEXT_LIGHT, bd=0, relief=FLAT, activebackground=BOTTOM_BAR_BG, cursor="hand2")
attach_btn.bind("<Button-1>", show_attach_menu)
attach_btn.pack(side=LEFT, padx=(0, 10))

entry_frame = Frame(input_area, bg=INPUT_FIELD_BG, bd=0)
entry_frame.pack(side=LEFT, fill=X, expand=True)

entry_msg = Entry(entry_frame, font=("Segoe UI", 11), bg=INPUT_FIELD_BG, fg=WA_TEXT_DARK, bd=0, relief=FLAT, highlightthickness=0)
entry_msg.pack(fill=X, ipady=8, padx=10)
entry_msg.bind("<Return>", send_text)

mic_btn = Button(input_area, text="🎤", font=("Segoe UI", 14), bg=BOTTOM_BAR_BG, fg=WA_TEXT_LIGHT, bd=0, relief=FLAT, activebackground=BOTTOM_BAR_BG, cursor="hand2", command=record_audio_toggle)
mic_btn.pack(side=LEFT, padx=10)

send_btn = Button(input_area, text="➤", font=("Segoe UI", 14), bg=BOTTOM_BAR_BG, fg=WA_GREEN, bd=0, relief=FLAT, activebackground=BOTTOM_BAR_BG, cursor="hand2", command=send_text)
send_btn.pack(side=LEFT)

rec_area = Frame(bottom_panel, bg=BOTTOM_BAR_BG, padx=15, pady=10)
del_rec_btn = Button(rec_area, text="🗑", font=("Segoe UI", 14), bg=BOTTOM_BAR_BG, fg="#EA4335", bd=0, relief=FLAT, activebackground=BOTTOM_BAR_BG, cursor="hand2", command=delete_audio)
del_rec_btn.pack(side=LEFT)
rec_status_lbl = Label(rec_area, text="", font=("Segoe UI", 10, "bold"), bg=BOTTOM_BAR_BG, fg="#EA4335")
rec_status_lbl.pack(side=LEFT, expand=True)
send_rec_btn = Button(rec_area, text="➤", font=("Segoe UI", 14), bg=BOTTOM_BAR_BG, fg=WA_GREEN, bd=0, relief=FLAT, activebackground=BOTTOM_BAR_BG, cursor="hand2", command=send_audio)
send_rec_btn.pack(side=RIGHT)

media_preview_frame = Frame(bottom_panel, bg="#FFFFFF", highlightbackground="#DDDDDD", highlightthickness=1)
preview_content_frame = Frame(media_preview_frame, bg="#FFFFFF", padx=10, pady=5)
preview_content_frame.pack(side=LEFT, fill=X, expand=True)
Label(preview_content_frame, text="Send Media", bg="#FFFFFF", fg=WA_GREEN, font=("Segoe UI", 8, "bold"), anchor=W).pack(anchor=W)
preview_lbl = Label(preview_content_frame, text="", bg="#FFFFFF", fg=WA_TEXT_DARK, font=("Segoe UI", 9), anchor=W, justify=LEFT)
preview_lbl.pack(anchor=W)
hd_var = BooleanVar()
hd_check = Checkbutton(preview_content_frame, text="HD", variable=hd_var, bg="#FFFFFF", font=("Segoe UI", 9, "bold"), fg=WA_TEXT_DARK, activebackground="#FFFFFF")
btn_confirm_preview = Button(media_preview_frame, text="✅ Send", command=confirm_send_media, bg=WA_GREEN, fg="white", font=("Segoe UI", 9, "bold"), relief=FLAT, padx=10)
btn_confirm_preview.pack(side=RIGHT, padx=5, pady=5)
btn_cancel_preview = Button(media_preview_frame, text="❌ Cancel", command=cancel_media_preview, bg="#EF4444", fg="white", font=("Segoe UI", 9, "bold"), relief=FLAT, padx=10)
btn_cancel_preview.pack(side=RIGHT, padx=5, pady=5)

reply_frame = Frame(bottom_panel, bg="#FFFFFF", highlightbackground="#DDDDDD", highlightthickness=1)
reply_content_frame = Frame(reply_frame, bg="#FFFFFF", padx=10, pady=5)
reply_content_frame.pack(side=LEFT, fill=X, expand=True)
Label(reply_content_frame, text="Reply", bg="#FFFFFF", fg=WA_GREEN, font=("Segoe UI", 8, "bold"), anchor=W).pack(anchor=W)
reply_lbl = Label(reply_content_frame, text="", bg="#FFFFFF", fg=WA_TEXT_LIGHT, font=("Segoe UI", 9, "italic"), anchor=W, justify=LEFT)
reply_lbl.pack(anchor=W)
cancel_rep_btn = Button(reply_frame, text="✕", font=("Segoe UI", 10), bg="#FFFFFF", fg=WA_TEXT_LIGHT, bd=0, relief=FLAT, activebackground="#FFFFFF", cursor="hand2", command=cancel_reply)
cancel_rep_btn.pack(side=RIGHT, padx=10)

# listens for incoming messages from the server in the background
def receive():
    buffer = b""
    while True:
        try:
            data = sock.recv(65536)
            if not data: break
            buffer += data
            while b"<EOF_MARKER>" in buffer:
                packet, buffer = buffer.split(b"<EOF_MARKER>", 1)
                process_packet(packet)
        except: break

threading.Thread(target=receive, daemon=True).start()

root.mainloop()