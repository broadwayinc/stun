import socket
import struct

def send_stun_binding_request(server_ip, server_port, client_port):
    stun_header = b'\x00\x01\x00\x00' + b'\x21\x12\xA4\x42' + (b'\x00' * 12)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    # Bind the socket to a specific port
    sock.bind(('', client_port))  # Bind to the chosen port on all interfaces

    try:
        sock.sendto(stun_header, (server_ip, server_port))
        data, _ = sock.recvfrom(1024)
        # print("Received response:", data)

        # Process STUN response
        message_type, message_length, magic_cookie = struct.unpack("!HHI", data[0:8])
        transaction_id = data[8:20]

        # Initialize pointer to start of attributes
        pointer = 20
        while pointer < message_length + 20:
            attr_type, attr_length = struct.unpack("!HH", data[pointer:pointer+4])
            attr_value = data[pointer+4:pointer+4+attr_length]

            if attr_type == 0x0001 or attr_type == 0x0020:  # MAPPED-ADDRESS or XOR-MAPPED-ADDRESS
                if attr_length == 8:  # IPv4
                    # Ensure attr_value is exactly 8 bytes
                    if len(attr_value) == 8:
                        _, family, port, ip1, ip2, ip3, ip4 = struct.unpack("!BBHBBBB", attr_value)
                        ip_address = f"{ip1}.{ip2}.{ip3}.{ip4}"
                        return f"{ip_address}:{port}"
                    else:
                        raise ValueError(f"Unexpected attr_value length for IPv4: {len(attr_value)}")
                elif attr_length == 20:  # IPv6
                    # Ensure attr_value is exactly 20 bytes for IPv6
                    if len(attr_value) == 20:
                        _, family, port, *ip_parts = struct.unpack("!BBH8H", attr_value)
                        ip_address = ':'.join(f"{part:04x}" for part in ip_parts)
                        return f"{ip_address}:{port}"
                    else:
                        raise ValueError(f"Unexpected attr_value length for IPv6: {len(attr_value)}")
                    
                break  # Exit after processing the relevant attribute

            pointer += 4 + attr_length  # Move to the next attribute

    finally:
        sock.close()


# Replace with your STUN server IP and port
server_ip = 'stun.broadwayinc.computer'
server_port = 53
client_port = 12345

ip = send_stun_binding_request(server_ip, server_port, client_port)
print(ip)