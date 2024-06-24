import json
import os
import boto3
import asyncio
from database_interface import query

sns = boto3.client("sns")
topic_arn = os.environ["WSFanSNS"]

apigw_management = boto3.client(
    "apigatewaymanagementapi", endpoint_url=os.environ["WEBSOCKET_ENDPOINT"]
)


async def send(cid, msg):
    try:
        apigw_management.post_to_connection(
            ConnectionId=cid,
            Data=json.dumps(msg),
        )

    except apigw_management.exceptions.GoneException:
        print(f"Connection ID {cid} is no longer available.")
        # Handle the disconnected client, e.g., remove the connection ID from your database

    except Exception as e:
        # Handle other exceptions
        print(f"An error occurred: {str(e)}")


def handler(event, context):
    for record in event["Records"]:
        message = json.loads(record["Sns"]["Message"])
        # Process the message
        print("Received message:", message)
        # Add your processing logic here

        """
        {
            "rid": "room_id",
            "sender": "sender_id",
            "content": "message_content",
            "startKey": "start_key"
        }
        """

        users = query(
            {
                "table": os.environ["WEBSOCKET_TABLE"],
                "hash": {"rid": message["rid"]},
                "search": {"cid": " "},
                "condition": ">",
                "limit": 1000,
                "projection": ["cid"],
                "primary": ["rid", "cid"],
                "startKey": message.get("startKey", None),
            }
        )

        if users["LastEvaluatedKey"]:
            message["startKey"] = users["LastEvaluatedKey"]
            sns.publish(TopicArn=topic_arn, Message=json.dumps(message))

        s_li = []
        for connection in users.get("Items", []):
            # if connection["cid"] != message.get("sender"):
            # Sending the message to the recipient's connection
            s_li.append(send(connection["cid"], message["content"]))

        if s_li:
            asyncio.get_event_loop().run_until_complete(asyncio.gather(*s_li))

    return {"status": "Message processed"}
