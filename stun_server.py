"""
Simple stun server, udp and tcp combined server on port 3560

Host on AWS EC2 instance forwarded from udp request load balancer(udp port:3468) infront.
tcp is only for health check running parallel with udp server.

free to ask any questions, happy to help.

- Baksa Gimm
"""

import socket
import struct
import threading
# STUN message types
STUN_BINDING_REQUEST = 0x0001
STUN_BINDING_RESPONSE = 0x0101

# STUN attribute types
STUN_ATTR_XOR_MAPPED_ADDRESS = 0x0020

# STUN magic cookie
STUN_MAGIC_COOKIE = 0x2112A442

def parse_stun_message(data):
    """
    Parses a STUN message and returns the method, message length, magic cookie, transaction ID, and attributes.
    """
    if len(data) < 20:
        return None, None, None, None, None

    method, message_length, magic_cookie = struct.unpack('!HHI', data[:8])
    transaction_id = data[8:20]

    if magic_cookie != STUN_MAGIC_COOKIE:
        return None, None, None, None, None

    attributes = data[20:20 + message_length]

    return method, message_length, magic_cookie, transaction_id, attributes

def create_stun_binding_response(transaction_id, ip, port):
    """
    Creates a STUN Binding Response message.
    """
    # STUN message header
    message_type = STUN_BINDING_RESPONSE
    message_length = 12  # Length of the XOR-MAPPED-ADDRESS attribute
    magic_cookie = STUN_MAGIC_COOKIE

    # XOR-MAPPED-ADDRESS attribute
    xor_mapped_address_type = 0x0020
    xor_mapped_address_length = 8
    xor_port = port ^ (magic_cookie >> 16)
    xor_ip = struct.unpack('!I', socket.inet_aton(ip))[0] ^ magic_cookie

    response = struct.pack('!HHI12sHHBBH4s',
                           message_type,
                           message_length,
                           magic_cookie,
                           transaction_id,
                           xor_mapped_address_type,
                           xor_mapped_address_length,
                           0x00,  # Reserved, should be 0
                           0x01,  # Address family (IPv4)
                           xor_port,
                           struct.pack('!I', xor_ip))

    return response

def handle_stun_request(server_socket):
    """
    Handles incoming STUN requests.
    """
    while True:
        data, client_address = server_socket.recvfrom(1024)
        method, message_length, magic_cookie, transaction_id, attributes = parse_stun_message(data)
        
        if method == STUN_BINDING_REQUEST:
            print(f"Received Binding Request from {client_address}")
            response = create_stun_binding_response(transaction_id, client_address[0], client_address[1])
            server_socket.sendto(response, client_address)
            print(f"Sent Binding Response to {client_address}")
        else:
            print(f"Received unknown method {method} from {client_address}")

def handle_tcp_health_check(client_socket, client_address):
    """
    Handles TCP health check requests.
    """
    print(f"Received health check request from {client_address}")
    health_check_response = "HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: 2\r\n\r\nOK"
    client_socket.sendall(health_check_response.encode('utf-8'))
    client_socket.close()

def start_combined_server(host='0.0.0.0', port=3560):
    """
    Starts a combined server that handles both STUN (UDP) and TCP health check requests on the same port.
    """
    # UDP socket for STUN
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_socket.bind((host, port))

    # TCP socket for health check
    tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    tcp_socket.bind((host, port))
    tcp_socket.listen(5)

    print(f"Combined server started on {host}:{port}")

    # Start thread to handle STUN requests
    stun_thread = threading.Thread(target=handle_stun_request, args=(udp_socket,))
    stun_thread.start()

    while True:
        client_socket, client_address = tcp_socket.accept()
        threading.Thread(target=handle_tcp_health_check, args=(client_socket, client_address)).start()

if __name__ == '__main__':
    start_combined_server()
