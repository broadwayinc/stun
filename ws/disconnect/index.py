import os
from database_interface import query, delete
import boto3
import json

sns = boto3.client("sns")
topic_arn = os.environ["WSFanSNS"]


def handler(event, context):
    print(event)
    connection_id = event["requestContext"]["connectionId"]
    websocket_tbl = os.environ["WEBSOCKET_TABLE"]
    # Delete the connection ID from the database

    print(connection_id, "Disconnecting...")

    to_disconnect = query(
        {
            "table": websocket_tbl,
            "hash": {
                "cid": connection_id,
            },
            "search": {"uid": " "},
            "condition": ">",
            "limit": 1000,
            "projection": ["cid", "uid", "rid", "cnd"],
        }
    )["Items"]

    if to_disconnect:
        del_params = []
        for td in to_disconnect:
            del_params.append({"cid": td["cid"], "uid": td["uid"]})
            if "rid" in td:
                sns.publish(
                    TopicArn=topic_arn,
                    Message=json.dumps(
                        {
                            "rid": td["rid"],
                            "content": {
                                "#notice": f'User "{td["uid"].split("#")[1]}" has left the message group;{td.get("cnd", "n/a")}',
                                "#user_id": td["uid"].split("#")[1],
                            },
                            "sender": td["cid"],
                        }
                    ),
                )

        delete({"table": websocket_tbl, "key": del_params})

    return {"statusCode": 200, "body": "Disconnected."}
