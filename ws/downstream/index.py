import json
import os
import boto3
from database_interface import update, delete

sqs = boto3.client("sqs")
sns = boto3.client("sns")
topic_arn = os.environ["WSFanSNS"]


def update_group(params):
    p = {
        "table": os.environ["WEBSOCKET_GROUP_TABLE"],
        "key": {"srvc": params["rid"].split("#")[0], "rid": params["rid"]},
        "item": {"cnt": f'*add {params["cnt"]}'},
    }

    if params["cnt"] < 0:
        p["exists"] = "rid"
        p["bypass_conditional_error"] = True

    update(p)

    if params["cnt"] < 0:
        sns.publish(
            TopicArn=topic_arn,
            Message=json.dumps(
                {
                    "rid": params["rid"],
                    "content": {
                        "#notice": f'User "{params["uid"].split("#")[1]}" has left the message group.',
                        "#user_id": params["uid"].split("#")[1],
                    },
                    "sender": params["cid"],
                }
            ),
        )


def remove_group(params):
    p = {
        "table": os.environ["WEBSOCKET_GROUP_TABLE"],
        "key": params,
    }

    delete(p)


actions = {"update_group": update_group, "remove_group": remove_group}


def handler(e, context):
    for r in e["Records"]:
        try:
            process = json.loads(r["body"])

            if process["action"] in actions:
                actions[process["action"]](process["params"])

            sqs.delete_message(
                QueueUrl=os.environ["DOWNSTREAM_WEBSOCKET_SQS_URL"],
                ReceiptHandle=r["receiptHandle"],
            )

        except Exception as err:
            print(err, function_name=context.function_name)
            raise err
