#!/usr/bin/env python3
import socket
import argparse
import struct

PACKET_SIZE   = 1400
PACKET_SINGLE = bytes.fromhex('FFFFFFFF') #byte/-1
PACKET_SPLIT  = bytes.fromhex('FFFFFFFE') #byte/-2

class BytesReader():
    def __init__(self, data):
        self.data = data
    def readByte(self):
        result, = struct.unpack_from('<B', self.data)
        self.data = self.data[1:]
        return result
    def readShort(self):
        result, = struct.unpack_from('<h', self.data)
        self.data = self.data[2:]
        return result
    def readLong(self):
        result, = struct.unpack_from('<l', self.data)
        self.data = self.data[4:]
        return result
    def readFloat(self):
        result, = struct.unpack_from('<f', self.data)
        self.data = self.data[4:]
        return result
    def readLongLong(self):
        result, = struct.unpack_from('<Q', self.data)
        self.data = self.data[8:]
        return result
    def readString(self):
        idx = 0
        while struct.unpack_from('<c', self.data, offset=idx)[0] != b'\x00':
            idx += 1
        result, = struct.unpack_from('<{}s'.format(idx), self.data)
        self.data = self.data[idx+1:]
        return result.decode()
    def readRemainder(self):
        return self.data.hex()

def send(sock, server, message):
    if len(message) < PACKET_SIZE:
        message = PACKET_SINGLE + message
        sock.sendto(message, server)
    else:
        raise NotImplementedError("split_send not implemented")

def recv(sock):
    data = bytearray(PACKET_SIZE)
    nbytes, address = sock.recvfrom_into(data)
    mv = memoryview(data)
    message_type = mv[0:4]
    if message_type == PACKET_SINGLE:
        return mv[4:nbytes]
    elif message_type == PACKET_SPLIT:
        raise NotImplementedError("Split read not implemented")

def as2_info(server):
    # Create socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    # Send request
    header = b'\x54'
    payload = b"Source Engine Query" + b'\x00'
    send(sock, server, header + payload)
    memory_view = recv(sock)

    reader = BytesReader(memory_view)
    response = {}
    response['Header']          = reader.readByte()
    response['Protocol']        = reader.readByte()
    response['Name']            = reader.readString()
    response['Map']             = reader.readString()
    response['Folder']          = reader.readString()
    response['Game']            = reader.readString()
    response['ID']              = reader.readShort()
    response['Players']         = reader.readByte()
    response['Max. Players']    = reader.readByte()
    response['Bots']            = reader.readByte()
    response['Server type']     = reader.readByte()
    response['Enviroment']      = reader.readByte()
    response['Visibility']      = reader.readByte()
    response['VAC']             = reader.readByte()
    response['Version']         = reader.readString()
    eof_flag                    = reader.readByte()
    if eof_flag & b'\x80'[0]:
        response['Port']        = reader.readByte()
    if eof_flag & b'\x10'[0]:
        response['SteamID']     = reader.readLongLong()
    if eof_flag & b'\x40'[0]:
        response['TV Port']     = reader.readShort()
        response['TV Host']     = reader.readString()
    if eof_flag & b'\x20'[0]:
        response['Keywords']    = reader.readString()
    if eof_flag & b'\01'[0]:
        response['GameID']      = reader.readLongLong()
    assert reader.readRemainder() == ''

    sock.close()
    return response

def as2_player(server):
    # Create socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    # Request challenge number
    header = b'\x55'
    payload = bytes.fromhex('FFFFFFFF')
    send(sock, server, header + payload)
    result = recv(sock)
    if result[0:1] != b'\x41':
        raise ValueError("Challenge header incorrect {}".format(result[0:1].hex()))
    
    # Send request with challenge number
    challenge_num = result[1:]
    send(sock, server, header + challenge_num)
    memory_view = recv(sock)

    #Send player request
    reader = BytesReader(memory_view)
    response = {}
    response['Header']      = reader.readByte()
    num_players             = reader.readByte()
    players = []
    for i in range(0, num_players):
        player = {}
        player['Index']     = reader.readByte()
        player['Name']      = reader.readString()
        player['Score']     = reader.readLong()
        player['Duration']  = reader.readFloat()
        players.append(player)
    
    response['Players'] = players
    sock.close()
    return response

def as2_rules(server):
    # Create socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    # Request challenge number
    header = b'\x56'
    payload = bytes.fromhex('FFFFFFFF')
    send(sock, server, header + payload)
    result = recv(sock)
    if result[0:1] != b'\x41':
        raise ValueError("Challenge header incorrect {}".format(result[0:1].hex()))
  
    # Send request with challenge number
    challenge_num = result[1:]
    send(sock, server, header + challenge_num)
    
    # Send rules request
    memory_view = recv(sock)
    reader = BytesReader(memory_view)
    response = {}
    response['Header']  = reader.readByte()
    num_rules           = reader.readShort()
    rules = []
    for i in range(0, num_rules):
        rule = {}
        rule['Name']    = reader.readString()
        rule['Value']   = reader.readString()
    
    response['Rules'] = rules

    sock.close()
    return response

if __name__ == '__main__':
    # Parse program arguments
    parser = argparse.ArgumentParser(description='Query information from a Steam game server')
    request_group = parser.add_mutually_exclusive_group()
    request_group.add_argument('-ri', '--info', action='store_true', help='Basic information about the server')
    request_group.add_argument('-rp', '--player', action='store_true', help='Details on each player on the server')
    request_group.add_argument('-rr', '--rules', action='store_true', help='Rules the server is using')
    parser.add_argument('-p', '--port', action='store', type=int, default=27015, help='Port to use')
    parser.add_argument('host')
    args = parser.parse_args()
    server = (args.host, args.port)

    # Execute request
    if args.info:
        result = as2_info(server)
    elif args.player:
        result = as2_player(server)
    elif args.rules:
        result = as2_rules(server)
    else:
        raise NotImplementedError("Request type not implemented")

    # Print results
    print(result)
 
