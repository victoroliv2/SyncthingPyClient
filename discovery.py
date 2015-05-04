import socket
import ipaddress

from config import *
from util   import *
from device_id import *
from serialize import *

def ip_to_string(b):
    if len(b) == 0:
        return ''
    elif len(b) == 4:
        return ipaddress.IPv4Address(b).exploded
    elif len(b) == 16:
        return ipaddress.IPv6Address(b).exploded
    else:
        assert(0)

def announcement(myID, serverID):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(40)
    sock.bind(('', 21025))
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)  
    
    print('Local discovery...')
    sock.sendto(pack_announce(myID), ('<broadcast>', 21025))

    tries = 0
    ret = None

    while True:
        if tries == 1:
            print('Global discovery...')
            sock.sendto(pack_query(serverID), (server_announce, 22026))
        elif tries > 1:
            break

        message , address = sock.recvfrom(1024)

        try:
            a, _ = unpack_announce(message)
        except socket.timeout:
            tries +=1
        except:
            sock.close()

        msg_address, _ = address

        if a['magic'] == 0x9D79BC39 and \
           a['device']['id'] == serverID:
            m = a['device']['addresses']
            if m:
                ret = (ip_to_string(m[0]['ip']) or msg_address, \
                       m[0]['port'] or 22000)
            else:
                ret = (msg_address, 22000)
            break

    sock.close()
    return ret
