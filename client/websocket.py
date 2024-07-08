import asyncio
import ssl
import base64
import hashlib
import json

async def send_message(writer, message):
    # Encode the message to bytes
    message_bytes = message.encode("utf-8")
    length = len(message_bytes)

    # Frame opcode for text is 0x1
    opcode = 0x81  # Final frame, text

    # Prepare the header
    if length <= 125:
        header = bytes([opcode, length])
    elif 126 <= length <= 65535:
        header = bytes([opcode, 126]) + length.to_bytes(2, "big")
    else:
        header = bytes([opcode, 127]) + length.to_bytes(8, "big")

    # Send the header followed by the payload
    writer.write(header + message_bytes)
    await writer.drain()


async def websocket_handshake(token: str, candidate: str, roomId: str):
    if not token:
        raise Exception("Token is required")

    if not candidate:
        raise Exception("Candidate is required")

    if not roomId:
        raise Exception("Room ID is required")

    host, path = (
        "yaqlgf8dek.execute-api.us-east-1.amazonaws.com",
        f"/api?token={token}",
    )

    port = 443  # Default HTTPS/WSS port

    # Generate a random WebSocket key
    websocket_key = base64.b64encode(hashlib.sha1().digest()).decode("utf-8")
    expected_accept = base64.b64encode(
        hashlib.sha1(
            (websocket_key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode("utf-8")
        ).digest()
    ).decode("utf-8")

    # SSL context for WSS
    ssl_context = ssl.create_default_context()

    # Connect and send handshake request
    reader, writer = await asyncio.open_connection(
        host, port, ssl=ssl_context, server_hostname=host
    )
    handshake_request = (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: {host}\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {websocket_key}\r\n"
        "Sec-WebSocket-Version: 13\r\n"
        "\r\n"
    )
    writer.write(handshake_request.encode("utf-8"))
    await writer.drain()

    # Read server response
    response = await reader.read(1024)

    if f"sec-websocket-accept: {expected_accept}" not in response.decode("utf-8"):
        raise Exception("WebSocket handshake failed")

    print("Handshake successful")

    # Start the WebSocket communication
    await send_message(
        writer,
        json.dumps(
            {
                "action": "joinRoom",
                "rid": roomId,
                "token": token,
                "candidate": candidate,
            }
        ),
    )

    try:
        while True:
            # Read the first two bytes to get opcode and payload length
            header = await reader.readexactly(2)
            opcode = header[0] & 0x0F
            length = header[1] & 0x7F

            # If it's a text frame (opcode 0x1)
            if opcode == 0x1:
                if length == 126:
                    # Next 2 bytes are the payload length
                    length_bytes = await reader.readexactly(2)
                    length = int.from_bytes(length_bytes, "big")
                elif length == 127:
                    # Next 8 bytes are the payload length
                    length_bytes = await reader.readexactly(8)
                    length = int.from_bytes(length_bytes, "big")

                # Now read the actual payload using the determined length
                payload = await reader.readexactly(length)
                text = payload.decode("utf-8")
                print("Received text:", text)

            # Handle ping frame (opcode 0x9)
            elif opcode == 0x9:
                # Send pong response (opcode 0xA)
                writer.write(b"\x8A\x00")  # Pong frame with no payload
                await writer.drain()

            # Handle pong frame (opcode 0xA) or close frame (opcode 0x8)
            elif opcode in (0x8, 0xA):
                # For simplicity, just print a message
                print("Received pong or close frame")
                break  # Exit loop if close frame

            # Wait a bit before the next operation
            await asyncio.sleep(1)

    except asyncio.CancelledError:
        # Close the connection gracefully
        writer.write(b"\x88\x00")  # WebSocket close frame
        await writer.drain()
        writer.close()
        await writer.wait_closed()
