import socket
import threading

# list to keep track of all connected users
clients = []

# this function manages everything for a single client connection
def handle_client(conn):
    clients.append(conn)
    buffer = b""
    try:
        while True:
            # wait for data chunks from the client
            data = conn.recv(65536)
            if not data:
                break
            
            # keep adding data to the buffer until we find the end marker
            buffer += data
            while b"<EOF_MARKER>" in buffer:
                packet, buffer = buffer.split(b"<EOF_MARKER>", 1)
                full_message = packet + b"<EOF_MARKER>"
                
                # send the message to everyone else except the person who sent it
                for client in clients:
                    if client != conn:
                        try:
                            client.sendall(full_message)
                        except:
                            pass
    except:
        pass
    finally:
        # clean up and remove the client when they disconnect
        if conn in clients:
            clients.remove(conn)
        conn.close()

# setting up the main server socket
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind(('0.0.0.0', 65432))
server.listen(5)

print("Server is listening on 0.0.0.0:65432....")

# keep accepting new connections in a loop
while True:
    conn, addr = server.accept()
    # start a new thread for each person so they can chat at the same time
    threading.Thread(target=handle_client, args=(conn,), daemon=True).start()