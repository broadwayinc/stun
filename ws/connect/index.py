
import os
from database_interface import put
from utils import authenticate_token, CustomError

def handler(event, context):
    if not event.get("queryStringParameters"):
        return {"statusCode": 401, "body": "Invalid token."}

    # Retrieve the access token from the query parameters

    try:
        token = authenticate_token(event["queryStringParameters"].get("token"))

    except CustomError as e:
        return {"statusCode": 401, "body": str(e)}

    user_id = token['user_id']
    service = token['service']

    connection_id = event["requestContext"]["connectionId"]

    put(
        {
            "table": os.environ["WEBSOCKET_TABLE"],
            "item": {
                "cid": connection_id,
                "uid": service + "#" + user_id,
            },
        }
    )

    return {"statusCode": 200, "body": "Connected."}