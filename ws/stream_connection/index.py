import os
import boto3
import json
import uuid

from database_interface import normalizer

sqs = boto3.client("sqs")
dynamodb = boto3.resource("dynamodb")
deserializer = boto3.dynamodb.types.TypeDeserializer()


def chunks(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


def main(event):
    # remove table info with no records

    to_sqs = []

    for e in event["Records"]:
        data = e["dynamodb"]
        old_data = (
            normalizer(
                {k: deserializer.deserialize(v) for k, v in data["OldImage"].items()}
            )
            if data.get("OldImage")
            else {}
        )

        new_data = (
            normalizer(
                {k: deserializer.deserialize(v) for k, v in data["NewImage"].items()}
            )
            if data.get("NewImage")
            else {}
        )

        if old_data.get("rid") != new_data.get("rid"):
            if old_data.get("rid"):
                to_sqs.append(
                    {
                        "action": "update_group",
                        "params": {
                            "rid": old_data["rid"],
                            "cnt": -1,
                            "uid": old_data["uid"],
                            "cid": old_data["cid"],
                            "cnd": old_data.get("cnd", "n/a"),
                        },
                    }
                )

            if new_data.get("rid"):
                to_sqs.append(
                    {
                        "action": "update_group",
                        "params": {
                            "rid": new_data["rid"],
                            "cnt": 1,
                            "uid": new_data["uid"],
                            "cid": new_data["cid"],
                            "cnd": new_data.get("cnd", "n/a"),
                        },
                    }
                )

    sqs_chunks = list(chunks(to_sqs, 10))
    for c in sqs_chunks:
        sqs.send_message_batch(
            QueueUrl=os.environ["DOWNSTREAM_WEBSOCKET_SQS_URL"],
            Entries=[
                {"Id": str(uuid.uuid4()), "MessageBody": json.dumps(body)} for body in c
            ],
        )


def handler(data, context):
    try:
        main(data)

    except Exception as err:
        print(err)

    return data
