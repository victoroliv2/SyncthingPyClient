from xdrlib import *

def bytearray2str(s):
    return "".join([chr(a) for a in s])

# XDRLIB SUCKS BALLS

def packer(f):
    def x(v):
        p = Packer()
        getattr(p, 'pack_' + f)(v)
        return p.get_buffer()
    return x

def packer_list(f):
    def x(v):
        p = Packer()
        p.pack_array(v, f)
        return p.get_buffer()
    return x

def unpacker(f):
    def x(msg):
        p = Unpacker(msg)
        decoded = getattr(p, 'unpack_' + f)()
        return decoded, msg[p.get_position():]
    return x

def unpacker_list(f):
    def x(msg):
        l = []
        size, s = unpack_uint(msg)
        for i in range(size):
            v, s = f(s)
            l.append(v)
        return l, s

    return x

def pack_dict(d, m):
    s = bytearray(b'')
    for k,f in m:
        s += f(d[k])
    return s

def unpack_dict(s, m):
    d = {}
    for k,f in m:
        decoded, s = f(s)
        d[k] = decoded
    return d, s

pack_uint   = packer('uint')
pack_uhyper = packer('uhyper')
pack_string = packer('string')

unpack_uint   = unpacker('uint')
unpack_uhyper = unpacker('uhyper')
unpack_string = unpacker('string')

def unpack_option(s):
    return unpack_dict(s,
            [('key',   unpack_string),
             ('value', unpack_string)])

def unpack_device(s):
    return unpack_dict(s,
            [('id'       , unpack_string),
             ('max_local_ver', unpack_uhyper),
             ('flags'    , unpack_uint),
             ('options'  , unpacker_list(unpack_option))])

def unpack_folder(s):
    return unpack_dict(s,
            [('id'       , unpack_string),
             ('devices'  , unpacker_list(unpack_device)),
             ('flags'    , unpack_uint),
             ('options'  , unpacker_list(unpack_option))])

def unpack_file(s):
    return unpack_dict(s,
            [('name'      , unpack_string),
             ('flags'     , unpack_uint),
             ('modified'  , unpack_uhyper),
             ('vector'    , unpacker_list(unpack_counter)),
             ('local_ver' , unpack_uhyper),
             ('blocks'    , unpacker_list(unpack_block))])

def unpack_counter(s):
    return unpack_dict(s,
            [('ID'    , unpack_uhyper),
             ('value' , unpack_uhyper)])

def unpack_block(s):
    return unpack_dict(s,
            [('size' , unpack_uint),
             ('hash' , unpack_string)])

def unpack_msgheader(s):
    header, s = unpack_uint(s)
    messageVersion = (header>>28) & 0xf
    messageId      = (header>>16) & 0xfff
    messageType    = (header>>8)  & 0xff
    compressed     = (header & 1)
    length, s = unpack_uint(s)
    assert(len(s) == 0)
    return messageVersion, messageId, messageType, compressed, length

def unpack_msgclusterconfig(s):
    return unpack_dict(s,
            [('client_name'    , unpack_string),
             ('client_version' , unpack_string),
             ('folders'        , unpacker_list(unpack_folder)),
             ('options'        , unpacker_list(unpack_option))])

def unpack_msgindex(s):
    return unpack_dict(s,
            [('folder'  , unpack_string),
             ('files'   , unpacker_list(unpack_file)),
             ('flags'   , unpack_uint),
             ('options' , unpacker_list(unpack_option))])

def unpack_msgresponse(s):
    return unpack_dict(s,
            [('data'  , unpack_string),
             ('code'  , unpack_uint)])

def unpack_msgping(s):
    return {}, ""
 
def unpack_msgpong(s):
    return {}, ""

def unpack_announce_address(s):
    return unpack_dict(s,
            [('ip'  , unpack_string),
             ('port', unpack_uint)])

def unpack_announce_device(s):
    return unpack_dict(s,
            [('id',        unpack_string),
             ('addresses', unpacker_list(unpack_announce_address))])

def unpack_announce(s):
    return unpack_dict(s,
            [('magic',         unpack_uint),
             ('device',        unpack_announce_device),
             ('extra_devices', unpacker_list(unpack_announce_device))])

def pack_option(option):
    return pack_dict(option,
            [('key',   pack_string),
             ('value', pack_string)])


def pack_device(device):
    return pack_dict(device,
            [('id'       , pack_string),
             ('max_local_ver', pack_uhyper),
             ('flags'    , pack_uint),
             ('options'  , packer_list(pack_option))])

def pack_folder(folder):
    return pack_dict(folder,
            [('id'       , pack_string),
             ('devices'  , packer_list(pack_device)),
             ('flags'    , pack_uint),
             ('options'  , packer_list(pack_option))])

def pack_counter(counter):
    return pack_dict(counter,
            [('ID',    pack_uhyper),
             ('value', pack_uhyper)])

def pack_block(block):
    return pack_dict(block,
            [('size', pack_uint),
             ('hash', pack_string)])

def pack_file(f):
    return pack_dict(f, [
    ('name'     , pack_string),
    ('flags'    , pack_uint),
    ('modified' , pack_uhyper),
    ('vector'   , packer_list(pack_counter)),
    ('local_ver', pack_uhyper),
    ('blocks'   , packer_list(pack_block))
    ])

def pack_msgheader(state, messageType, length):
    header = ((state.protocolVersion & 0xf)   << 28) + \
             ((state.messageID       & 0xfff) << 16) + \
             ((messageType           & 0xff)  << 8 ) + \
             (state.compression & 1)
    state.bumpID()

    s = pack_uint(header) + pack_uint(length)
    return s

def pack_msgclusterconfig(state, folders):
    content = bytearray(b'')
    content += pack_string(state.clientName)
    content += pack_string(state.clientVersion)
    content += packer_list(pack_folder)(folders)
    content += packer_list(pack_option)([])
    return pack_msgheader(state, 0, len(content)) + content

def pack_msgindex(state, folder):
    content = bytearray(b'')
    content += pack_string(folder['id'])
    content += packer_list(pack_file)(folder['files'])
    content += pack_uint(0)
    content += packer_list(pack_option)([])
    return pack_msgheader(state, 1, len(content)) + content

def pack_msgrequest(state, folder, filename, offset, size, blockhash):
    content = bytearray(b'')
    content += pack_string(folder)
    content += pack_string(filename)
    content += pack_uhyper(offset)
    content += pack_uint(size)
    content += pack_string(blockhash)
    content += pack_uint(0)
    content += packer_list(pack_option)([])
    return pack_msgheader(state, 2, len(content)) + content

def pack_announce(myID):
    content = bytearray(b'')
    content += pack_uint(0x9D79BC39)
    content += pack_string(myID)
    content += pack_uint(0)
    content += pack_uint(0)
    return content

def pack_query(serverID):
    content = bytearray(b'')
    content += pack_uint(0x2CA856F5)
    content += pack_string(serverID)
    return content
