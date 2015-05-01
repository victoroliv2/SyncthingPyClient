import os

HOST = "127.0.0.1"
PORT = 22000

server_address = (HOST, PORT)

ssl_cert_file = os.path.join(os.getcwd(), "data/cert.pem")
ssl_key_file  = os.path.join(os.getcwd(), "data/key.pem")
