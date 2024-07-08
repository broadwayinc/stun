import boto3
import json
import os

from database_interface import query, update
from utils import authenticate_token, CustomError

sns = boto3.client("sns")
topic_arn = os.environ["WSFanSNS"]

apigw_management = boto3.client(
    "apigatewaymanagementapi", endpoint_url=os.environ["WEBSOCKET_ENDPOINT"]
)


def broadcast(message, event):
    room_id = message["rid"]

    try:
        token = authenticate_token(message["token"])

    except CustomError as e:
        return {"statusCode": 401, "body": str(e)}

    sid = token["service"]

    msg = {
        "#message": message["content"],
        "#user_id": token["user_id"],
    }

    sns.publish(
        TopicArn=topic_arn,
        Message=json.dumps(
            {
                "rid": sid + "#" + room_id,
                "sender": event["requestContext"]["connectionId"],
                "content": msg,
            }
        ),
    )

    return {
        "statusCode": 200,
        "body": "Broadcasted message to users.",
    }


def sendMessage(message, event):
    user_id = message["uid"]
    recipient_connection_id = None

    try:
        token = authenticate_token(message["token"])

    except CustomError as e:
        return {"statusCode": 401, "body": str(e)}

    sender = token["user_id"]
    sid = token["service"]

    try:
        # retrieve the recipient's connection ID from the database
        recipient_connection_id = query(
            {
                "table": os.environ["WEBSOCKET_TABLE"],
                "hash": {"uid": sid + "#" + user_id},
                "search": {"cid": " "},
                "condition": ">",
                "primary": ["uid", "cid"],
                "limit": 1,
            }
        )["Items"]

        if not recipient_connection_id:
            return {"statusCode": 400, "body": "Recipient is not connected."}

        recipient_connection_id = recipient_connection_id[0]["cid"]

    except Exception as e:
        print(f"An error occurred: {str(e)}")
        return {"statusCode": 500, "body": "Failed to send message."}

    # wss://${WebSocketApi}.execute-api.${AWS::Region}.amazonaws.com/api

    print(recipient_connection_id, "Sending message...")
    # Sending the message to the recipient's connection

    msg = {"#private": message["content"], "#user_id": sender}

    msg = json.dumps(msg)

    try:
        apigw_management.post_to_connection(
            ConnectionId=recipient_connection_id, Data=msg
        )

    except apigw_management.exceptions.GoneException:
        print(f"Connection ID {recipient_connection_id} is no longer available.")
        # Handle the disconnected client, e.g., remove the connection ID from your database
        return {"statusCode": 400, "body": "Recipient is not connected."}

    except Exception as e:
        # Handle other exceptions
        print(f"An error occurred: {str(e)}")
        return {"statusCode": 500, "body": "Failed to send message."}

    try:
        apigw_management.post_to_connection(
            ConnectionId=event["requestContext"]["connectionId"], Data=msg
        )

    except apigw_management.exceptions.GoneException:
        print(f"Connection ID {recipient_connection_id} is no longer available.")
        # Handle the disconnected client, e.g., remove the connection ID from your database
        return {"statusCode": 400, "body": "Recipient is not connected."}

    except Exception as e:
        # Handle other exceptions
        print(f"An error occurred: {str(e)}")
        return {"statusCode": 500, "body": "Failed to send message."}

    return {
        "statusCode": 200,
        "body": "Sent message to " + user_id + ".",
    }


def joinRoom(message, event):
    connection_id = event["requestContext"]["connectionId"]
    room_id = message["rid"]
    cand = message.get("candidate", "n/a")

    try:
        token = authenticate_token(message["token"])

    except CustomError as e:
        return {"statusCode": 401, "body": str(e)}

    uid = token["user_id"]
    sid = token["service"]

    item = {
        "rid": sid + "#" + room_id,
        "cnd": cand,
    }

    try:
        if room_id:
            update(
                {
                    "table": os.environ["WEBSOCKET_TABLE"],
                    "key": {
                        "cid": connection_id,
                        "uid": sid + "#" + uid,
                    },
                    "item": item,
                    "exists": "uid",
                }
            )
            """
                "rid": "room_id",
                "sender": "sender_id",
                "content": "message_content",
            """

            sns.publish(
                TopicArn=topic_arn,
                Message=json.dumps(
                    {
                        "rid": sid + "#" + room_id,
                        "sender": connection_id,
                        "content": {
                            "#notice": f'User "{uid}" has joined the message group;{cand}',
                            "#user_id": uid,
                        },
                    }
                ),
            )

        else:
            update(
                {
                    "table": os.environ["WEBSOCKET_TABLE"],
                    "key": {
                        "cid": connection_id,
                        "uid": sid + "#" + uid,
                    },
                    "remove": ["rid", "cnd"],
                    "exists": "uid",
                }
            )

            return {
                "statusCode": 200,
                "body": "User has left the message group.",
            }

    except Exception as e:
        print(e, "Failed to join message group.")
        return {"statusCode": 400, "body": "Failed to join message group."}

    return {
        "statusCode": 200,
        "body": 'Joined message group: "' + room_id + '".',
    }


def handler(event, context):
    print(event)

    message = json.loads(event["body"])

    print(message, "Message received")

    if message["action"] == "sendMessage":
        return sendMessage(message, event)

    if message["action"] == "joinRoom":
        return joinRoom(message, event)

    if message["action"] == "broadcast":
        return broadcast(message, event)
