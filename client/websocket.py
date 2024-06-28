import asyncio
import ssl
import base64
import hashlib


async def websocket_handshake():
    # Extract host and path from URI
    # Ensure this parsing accounts for the stage in the path for AWS API Gateway
    scheme, host, path = (
        "wss",
        "yaqlgf8dek.execute-api.us-east-1.amazonaws.com",
        "/api?token=bobocar",
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

    try:
        while True:
            # Read the first two bytes to get opcode and payload length
            header = await reader.readexactly(2)
            opcode = header[0] & 0x0f
            length = header[1] & 0x7f

            # If it's a text frame (opcode 0x1)
            if opcode == 0x1:
                # Assuming payload is less than 126 for simplicity
                payload = await reader.readexactly(length)
                text = payload.decode('utf-8')
                print("Received text:", text)

            # Handle ping frame (opcode 0x9)
            elif opcode == 0x9:
                # Send pong response (opcode 0xA)
                writer.write(b'\x8A\x00')  # Pong frame with no payload
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
        writer.write(b'\x88\x00')  # WebSocket close frame
        await writer.drain()
        writer.close()
        await writer.wait_closed()


asyncio.run(
    websocket_handshake()
)
