import os

HOST = "192.168.42.79"
PORT = 22000
#server_address = (HOST, PORT)
server_address = None

server_announce = 'announce.syncthing.net'
server_deviceid = "OCHOGFI-6W4QB6X-QCW5OIQ-FK5532Q-AEQLVGK-RHOI4TN-J2BKKGV-262TCAD"

ssl_cert_file = os.path.join(os.getcwd(), "data/cert.pem")
ssl_key_file  = os.path.join(os.getcwd(), "data/key.pem")
