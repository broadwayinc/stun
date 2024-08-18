import asyncio

from stun_client import stun_client
from get_users import get_users
from websocket import websocket_handshake

stun_server = "stun.broadwayinc.computer:3468"  # 'stun.server:port
client_port = 12345
token = "user_id"
roomId = "Id001"

ip = stun_client(stun_server, client_port)
print("ip:", ip)  # ip:port

# make websocket connection, join room
websocket = websocket_handshake(token, ip, roomId)

# get users that is currently in the room
users = get_users(roomId)  # [{'cnd': 'ip:port', 'uid': 'stunpunch#user_id'}, ...]
print("- users in the room -")
print(users)  # users in the room

# keep running websocket in parallel and get noted when users join/leave
asyncio.run(websocket)
