#
# Syncthing Client
# Victor Oliveira
# victor@doravel.me
#

import socket
import os
import sys
from datetime import datetime

import lz4
from hashlib import sha256
import ssl

MSG_CLUSTERCONFIG = 0
MSG_INDEX = 1
MSG_REQUEST = 2
MSG_RESPONSE = 3
MSG_PING = 4
MSG_PONG = 5
MSG_INDEX_UPDATE = 6
MSG_CLOSE = 7

from util import *
from device_id import *
from serialize import *
from discovery import *
from config import *

class State:
    def __init__(self, ssl_cert_file):
        self.messageID = 0
        self.compression = 0

        self.protocolVersion = 0

        self.clientName    = b"SyncThingPy"
        self.clientVersion = b"v0.0.1"

        self.folder_base = ''
        self.registered_folders = []

        self.stage = 0

        with open(ssl_cert_file, 'r') as f:
            v = ssl.PEM_cert_to_DER_cert(f.read())
            self.deviceID = sha256(v).digest()
            print('My DeviceID: %s' % get_device_id(self.deviceID))

    def bumpID(self):
        self.messageID += 1
        if self.messageID > 0xfff:
            self.messageID = 0

class MessageProcessor:
    messageUnpack  = { MSG_CLUSTERCONFIG : unpack_msgclusterconfig,
                       MSG_INDEX        : unpack_msgindex,
                       MSG_INDEX_UPDATE : unpack_msgindex,
                       MSG_RESPONSE     : unpack_msgresponse,
                       MSG_PING         : unpack_msgping,
                       MSG_PONG         : unpack_msgpong }

    def __init__(self, state, socket):
        self.state = state
        self.socket = socket
        self.server_down = 0

    def send_greetings(self):
        msg_cc, _    = self.receive_message(MSG_CLUSTERCONFIG)
        self.process_msgclusterconfig(msg_cc)

        folders = []
        for folder_name in self.state.registered_folders:
            folders.append( self.scan_folder(folder_name) )

        send_message(self.socket, pack_msgclusterconfig(self.state, folders))

        for folder in folders:
            print('Send Index for folder: %s' % folder['id'])
            send_message(self.socket, pack_msgindex(self.state, folder))

        n_folders = len(msg_cc['folders'])
        for i in range(n_folders):
            msg_index, _ = self.receive_message(MSG_INDEX)
            self.process_msgindex(msg_index)

    def scan_folder(self, folder_name):
        assert(type(folder_name) == bytearray)
        folder = \
        {'files'     : [], # implement this
         'id'        : folder_name,
         'devices'   : [{'id'            : state.deviceID,
                         'max_local_ver' : 0,
                         'flags'         : 0,
                         'options'       : []}],
         'flags'     : 0,
         'options'   : []}
        return folder

    def send_ping(self):
        print('SEND PING!')
        send_message(self.socket, pack_msgheader(self.state, MSG_PING, 0))
        self.receive_message(MSG_PONG)
        print('GOT PONG!')

    def send_pong(self):
        print('SEND PONG!')
        send_message(self.socket, pack_msgheader(self.state, MSG_PONG, 0))

    def send_pong(self):
        send_message(self.socket, pack_msgheader(self.state, MSG_CLOSE, 0))

    def receive_message(self, expected=None):
        msgheader = recv_data(self.socket, 8)
        messageVersion, messageId, messageType, compressed, length = unpack_msgheader(msgheader)

        data = recv_data(self.socket, length)

        #print(messageVersion, messageId, messageType, compressed, length)
        
        if compressed:
            data = bytearray(lz4.loads(bytes(data)))

        if expected:
            assert(messageType == expected or messageType in expected)

        if messageType in self.messageUnpack:
            msgdict, rest = self.messageUnpack[messageType](data)
            assert(len(rest) == 0) # consumed
        else:
            msgdict = {}
            print("message type {} not defined yet.".format(messageType))

        return msgdict, messageType

    def wait(self):
        msg, msgType = None, None
        server_down = False

        try:
            msg, msgType = self.receive_message([MSG_INDEX, MSG_INDEX_UPDATE, MSG_RESPONSE,
                                                 MSG_PING, MSG_CLOSE])
        except socket.timeout:
            try:
                self.send_ping()
            except socket.timeout:
                server_down = True
                print('Server timeout!')
        except ConnectionResetError:
            print('Connection Reset!')
            server_down = True
        finally:
            if server_down:
                self.send_close()
                return False

        if msgType in [MSG_INDEX, MSG_INDEX_UPDATE]:
            self.process_msgindex(msg)
        elif msgType == MSG_PING:
            self.send_pong()
        elif msgType == MSG_CLOSE:
            return False

        return True

    def process_msgclusterconfig(self, msg):
        self.state.registered_folders = [folder['id'] for folder in msg['folders']]
        print("Folders: ", [f.decode("utf-8") for f in self.state.registered_folders])

    def download(self, state, oldfd, newfd, folder, filename, offset, block_size, block_hash):
        assert(len(block_hash) == 32)

        newfd.seek(offset)

        if oldfd:
            oldfd.seek(offset)
            olddata = oldfd.read(block_size)
            oldhash = sha256(olddata).digest()
            assert(len(oldhash) == 32)
            if oldhash == block_hash:
                newfd.write(olddata)
                return 1

        send_message(listen_sock, pack_msgrequest(state, folder, filename, offset, block_size, block_hash))
        msg_resp, _ = self.receive_message(MSG_RESPONSE)

        if (msg_resp['code'] != 0):
            return 0

        data = msg_resp['data']
        newfd.write(data)

        print('Got %d bytes for %s' % (len(data), filename))

        return 2

    def process_msgindex(self, msg):
        folder = msg['folder']
        files  = msg['files']
        max_block_size = 131072

        folder_path = os.path.join(self.state.folder_base, bytearray2str(folder))
        if not os.path.isdir(folder_path):
            os.makedirs(folder_path, exist_ok=True)
            print('Creating dir %s' % folder_path)

        for f in files:
            filename = f['name']
            blocks = f['blocks']
            file_path = os.path.join(folder_path, bytearray2str(filename))
            tmp_file_path = file_path+".tmp"
            exists = os.path.isfile(file_path) 
            size = sum([b['size'] for b in blocks])

            if size == 0:
                if exists:
                    if backup_mode:
                        backup_file(file_path)
                    else:
                        os.remove(file_path)
                continue

            ok = True
            with open(tmp_file_path, 'wb') as newfile:
                newfile.write(b'\0' * size)
                
                if exists:
                    oldsize = os.path.getsize(file_path)
                    oldfile = open(file_path, 'rb')
                else:
                    oldsize = -1
                    oldfile = None

                file_changed = False

                for i, block in enumerate(blocks):
                    off_start = i * max_block_size
                    block_size = min(max_block_size, size-off_start)
                    off_end = off_start + block_size - 1
                    old_contained = off_end < oldsize
                    ret = self.download(self.state,
                                      oldfile if old_contained else None,
                                      newfile,
                                      folder,
                                      filename,
                                      off_start,
                                      block_size,
                                      block['hash'])
                    if ret == 0:
                        ok = False
                        break
                    elif ret == 2:
                        file_changed = True

                if oldfile: oldfile.close()

            if ok and file_changed:
                if exists:
                    if backup_mode: backup_file(file_path)
                    else:           os.remove(file_path)
                os.rename(tmp_file_path, file_path)
            elif not ok:
                print("Something bad happened, deleting %s" % (tmp_file_path))
                os.remove(tmp_file_path)

if __name__ == "__main__":
    state = State(ssl_cert_file)
    state.folder_base = 'sync'

    if not server_address:
        server_address = announcement(state.deviceID, get_device_id_from_string(server_deviceid))

        if server_address:
            print('Server found: %s:%s' % server_address)
        else:
            print('Server not found')
            sys.exit(1)

    listen_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listen_sock.settimeout(20)

    listen_sock = ssl.wrap_socket(listen_sock,
                                  keyfile=ssl_key_file,
                                  certfile=ssl_cert_file,
                                  ssl_version=ssl.PROTOCOL_TLSv1_2)

    listen_sock.connect(server_address)

    messageProcessor = MessageProcessor(state, socket)

    msgProc = MessageProcessor(state, listen_sock)
    msgProc.send_greetings()
    msgProc.send_ping()

    while True:
        r = msgProc.wait()
        if not r: sys.exit(0)
