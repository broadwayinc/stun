import os
from utils import digest_event, send, CustomError
from database_interface import query


def main(e):
    request = e["data"]
    startKey = request.get("startKey", None)
    limit = request.get("limit", 1000)
    service = "".join(e for e in os.environ["SERVICE"] if e.isalnum())
    ascending = request.get("ascending", True)

    if request.get("searchFor"):
        if request["searchFor"] == "room":
            return query(
                {
                    "table": os.environ["WEBSOCKET_GROUP_TABLE"],
                    "hash": {"srvc": service},
                    "search": {
                        "rid": service + f'#{request.get("value", "")}',
                    },
                    "condition": request.get("condition", ">="),
                    "limit": limit,
                    "startKey": startKey,
                    "projection": ["rid", "cnt"],
                    "ascending": ascending,
                },
                True,
            )
        
        elif request["searchFor"] == "number_of_users":
            return query(
                {
                    "table": os.environ["WEBSOCKET_GROUP_TABLE"],
                    "hash": {"srvc": service},
                    "search": {"cnt": request.get("value", 0)},
                    "condition": request.get("condition", ">="),
                    "limit": limit,
                    "primary": ["srvc", "cnt"],
                    "startKey": startKey,
                    "projection": ["rid", "cnt"],
                    "ascending": ascending,
                },
                True,
            )

    else:
        if not request.get("room", None):
            raise CustomError(
                os.environ["ERR_INVALID_PARAMETER"] + f': "room" is required.'
            )

        user_id = request.get("user_id", None)

        if user_id:
            ul = query(
                {
                    "table": os.environ["WEBSOCKET_TABLE"],
                    "hash": {
                        "uid": service + "#" + user_id,
                    },
                    "search": {
                        "cid": " ",
                    },
                    "condition": ">",
                    "limit": 1,
                    "projection": ["uid", "rid", "cnd"],
                    "primary": ["uid", "cid"],
                }
            )

            ul_items = []

            if ul["Items"]:
                i = ul["Items"][0]
                if request["room"] == i["rid"].split("#")[1]:
                    ul_items.append({"uid": i["uid"]})
                else:
                    ul["Items"] = []

            ul["Items"] = ul_items

            return ul

        return query(
            {
                "table": os.environ["WEBSOCKET_TABLE"],
                "hash": {
                    "rid": service + "#" + request["room"],
                },
                "search": {
                    "cid": " ",
                },
                "condition": ">",
                "primary": ["rid", "cid"],
                "limit": limit,
                "startKey": startKey,
                "projection": ["uid", "cnd"],
                "ascending": ascending,
            }
        )


type_check = {
    "room": str,
    "user_id": str,
    "limit": int,
    "startKey": dict,
    "ascending": bool,
}


def handler(event, context):
    try:
        data = main(digest_event(event, data_type=type_check))
        endOfList = False if data["LastEvaluatedKey"] else True
        data = {
            "list": data["Items"],
            "startKey": "end" if endOfList else data["LastEvaluatedKey"],
            "endOfList": endOfList,
        }
        return send(200, data)

    except Exception as err:
        return send(400, err)
