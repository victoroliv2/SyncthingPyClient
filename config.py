import os

HOST = "127.0.0.1"
PORT = 22000
#server_address = (HOST, PORT)
server_address = None # do not discover

server_announce = 'announce.syncthing.net'
server_deviceid = 'AAAAAAA-BBBBBBB-CCCCCCC-DDDDDDD-EEEEEEE-FFFFFFF-GGGGGGG-HHHHHHH'

# do not delete files
backup_mode = False

ssl_cert_file = os.path.join(os.getcwd(), "data/cert.pem")
ssl_key_file  = os.path.join(os.getcwd(), "data/key.pem")
