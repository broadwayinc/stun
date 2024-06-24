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

        new_data = (
            normalizer(
                {k: deserializer.deserialize(v) for k, v in data["NewImage"].items()}
            )
            if data.get("NewImage")
            else {}
        )

        if new_data.get("cnt") == 0:
            to_sqs.append(
                {
                    "action": "remove_group",
                    "params": {
                        "srvc": new_data["rid"].split("#")[0],
                        "rid": new_data["rid"],
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
