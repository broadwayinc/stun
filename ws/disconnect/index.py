import os
from database_interface import query, delete


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
            "projection": ["cid", "uid"],
        }
    )["Items"]

    if to_disconnect:
        delete({"table": websocket_tbl, "key": to_disconnect})

    return {"statusCode": 200, "body": "Disconnected."}
