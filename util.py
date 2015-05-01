def bytearray2str(s):
    return "".join([chr(a) for a in s])

def recv_data(socket, MSGLEN):
    # remaining = number of bytes being received (determined already)
    msg = bytearray()
    bytes_recd = 0
    remaining = MSGLEN
    while remaining > 0:
        chunk = socket.recv(min(MSGLEN - bytes_recd, 2048))
        msg.extend(chunk)            # Add to message
        bytes_recd =+ len(chunk)
        remaining -= len(chunk)  
    return msg

def send_message(socket, msg):
    if not socket.sendall(msg):
        assert(0)


