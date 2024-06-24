import boto3
import botocore
from boto3.dynamodb.conditions import Key, Attr, Not
from boto3.dynamodb.types import Binary
import decimal
import base64
import json
from pprint import pprint

db = boto3.resource("dynamodb")
dynamodb = {}

sep = "*" * 10
valid_conditions = [
    ">",
    ">=",
    "=",
    "<",
    "<=",
    "!=",
    "gt",
    "gte",
    "eq",
    "lt",
    "lte",
    "ne",
]

def chunks(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


def normalizer(obj, resolver=None):
    if isinstance(obj, list):
        # loops backward to be able to remove items
        for i in range(len(obj) - 1, -1, -1):
            obj[i] = normalizer(obj[i], resolver=resolver)

            if obj[i] == "__DELETE__":
                del obj[i]

        return obj

    elif isinstance(obj, dict):
        # loop keys
        for k in list(obj):
            if k in obj:
                if resolver and callable(resolver):
                    res = resolver(obj, k)

                    if res == "__DELETE__":
                        # delete key
                        return "__DELETE__"

                    if not obj:
                        # is falsy data, continue to next item
                        # this happens when the whole item is removed from the callback
                        break

                    if not k in obj:
                        # if key does not remain
                        # this happens when the item key was is removed from the callback
                        continue

                    if res == "__PASS__":
                        # continue without normalizing
                        return obj[k]

                obj[k] = normalizer(obj[k], resolver=resolver)

        return obj

    elif isinstance(obj, set):
        # returns set type to list
        lst = list(obj)
        lst.sort()
        return lst

    elif isinstance(obj, Binary):
        return base64.b64encode(obj.value).decode("ascii")

    elif isinstance(obj, decimal.Decimal):
        if obj % 1 == 0:
            return int(obj)
        else:
            return float(obj)

    else:
        return obj



def prepare_table(table):
    if isinstance(table, str):
        if not table in dynamodb:
            dynamodb[table] = db.Table(table)

        table = dynamodb[table]

    return table


def query(params, normalize=False):
    """

    Queries dynamodb database.

    Use example:
        query({
            'table': 'TableName',
            'hash': {'hash': 'value'},
            'search': {'range': ['start', 'end'] },
            'primary': True,
            'condition': '=', # irrelevant for range search
            'limit': 100,
            'filter': {
                'not': False,
                'key': 'where',
                'conditions': {'condition': 'value'},
            },
            'ascending': bool,
            'projection': ['attr1', 'attr2']
        }, normalize=True)

    --

    params : dict
        table : str | DynamodbTable
            Dynamodb table object | table name string

        hash : dict
            Hash key object. { "key_name": "key value" }

        search : dict
            Attribute, and value to query. { "attribute_name": "attribute value" }
            For range query, { "attribute_name": ["value start", "value end"] }

        primary : bool | list (default=True)
            True if search attribute is a part of primary index, False for local secondary index.
            Use list for global secondary index.

        condition : str (default='=')
            Query condition for search.
            Charaters below are accepted:
                '<', '<=', '=', '>', '>=', '=', '!=', 'gt', 'gte', 'lt', 'lte', 'eq', 'ne'

            Condition becomes irrelevant when search is a range query.

        limit : int (default=100)
            Limits number of record for each fetch.

        startKey : dict
            Value for ExclusiveStartKey.
            Used for list startKey.

        filter : dict
            Filter condition for fetched data.
            {
                'not': False, # Excludes when True
                'conditions': {
                    'condition': https://boto3.amazonaws.com/v1/documentation/api/latest/reference/customizations/dynamodb.html#dynamodb-conditions
                },
                'key': 'attribute name' # Attribute name
            }

        projection : list
            List of attribute names to fetch.

    normalize : bool | callable
        When True, normalize decimals to int, binary to base64 string, sets to list.
        Custom normalizing can be done by passing function.

        Example:
            def custom(obj, key):
                # obj is current looping dictionary
                # key is current key

                obj[key] = 'Replace value'
                obj['new_key'] = 'This will not be normalized'

                return '__DELETE__' # deletes whole item from list
                return '__PASS__' # continue without normalizing

            query(params, custom)

    late ascii char: 􏿿

    """

    print("\n{}[QUERY PARAMS START]{}\n".format(sep, sep))
    pprint(params, width=1024, depth=4)
    print("\n{}[QUERY PARAMS END]{}\n".format(sep, sep))

    try:
        # required params
        table = prepare_table(params["table"])
        hash = params["hash"]
        search = params["search"] if "search" in params else None

    except:
        raise Exception("query: required parameter is missing.")

    ascending = True
    attribute_name = None

    if not hash or isinstance(hash, dict):
        hash_name = list(hash.keys())[0]
        hash_value = hash[hash_name]
        attribute_name = hash_name
    else:
        raise Exception('query: "hash" needs to be a dictionary.')

    KeyConditionExpression = Key(hash_name).eq(hash_value)

    # for logging
    Log_KeyConditionExpression = "Key({}).eq({})".format(hash_name, hash_value)
    value = None
    value_range = None

    if search and isinstance(search, dict):
        attribute_name = list(search.keys())[0]
        value = search[attribute_name]

        if isinstance(value, list):
            # if list is given, bypass condition
            if "condition" in params:
                del params["condition"]

            a = value[0]
            b = value[1]

            if a != b:
                if a < b:
                    value = a
                    value_range = b
                else:
                    value = b
                    value_range = a
                    ascending = False
            else:
                value = a
                params["condition"] = "="

        elif isinstance(value, str):
            if "condition" in params and params["condition"]:
                # condition on string
                # > : greater than given string in lexographic order
                # <, <= : lesser than given string in lexographic order
                # >= : starts with

                params["condition"] = condition_converter(params["condition"])

                if params["condition"] == ">=":
                    value_range = value + "􏿿"

                elif params["condition"] == "<=":
                    params["condition"] = "="

    ###############################################################################################
    # optional parameters

    primaryIndex = (
        params["primary"]
        if "primary" in params
        and (
            isinstance(params["primary"], bool)
            or isinstance(params["primary"], list)
            or isinstance(params["primary"], str)
            and params["primary"]
        )
        else True
    )

    condition = (
        condition_converter(params["condition"])
        if "condition" in params and params["condition"]
        else "="
    )

    limit = (
        params["limit"]
        if "limit" in params and isinstance(params["limit"], int)
        else 100
    )

    if limit > 1000:
        # limit fetch to 1000
        limit = 1000

    startKey = (
        params["startKey"]
        if "startKey" in params and isinstance(params["startKey"], dict)
        else {}
    )

    filter = (
        params["filter"]
        if "filter" in params and isinstance(params["filter"], dict)
        else None
    )

    projection = (
        params["projection"]
        if "projection" in params and isinstance(params["projection"], list)
        else []
    )

    ###############################################################################################

    if isinstance(value, float):
        value = decimal.Decimal(str(value))

    if isinstance(value_range, float):
        value_range = decimal.Decimal(str(value_range))

    # setup query
    if value_range != None:
        value_pair = [value, value_range]
        KeyConditionExpression = KeyConditionExpression & Key(attribute_name).between(
            *value_pair
        )
        Log_KeyConditionExpression += " & Key({}).between({},{})".format(
            attribute_name, *value_pair
        )
    elif value:
        if condition == ">":
            KeyConditionExpression = KeyConditionExpression & Key(attribute_name).gt(
                value
            )
            Log_KeyConditionExpression += " & Key({}).gt({})".format(
                attribute_name, value
            )
        elif condition == ">=":
            KeyConditionExpression = KeyConditionExpression & Key(attribute_name).gte(
                value
            )
            Log_KeyConditionExpression += " & Key({}).gte({})".format(
                attribute_name, value
            )
        elif condition == "=":
            KeyConditionExpression = KeyConditionExpression & Key(attribute_name).eq(
                value
            )
            Log_KeyConditionExpression += " & Key({}).eq({})".format(
                attribute_name, value
            )
        elif condition == "<=":
            KeyConditionExpression = KeyConditionExpression & Key(attribute_name).lte(
                value
            )
            Log_KeyConditionExpression += " & Key({}).lte({})".format(
                attribute_name, value
            )
            ascending = False
        elif condition == "<":
            KeyConditionExpression = KeyConditionExpression & Key(attribute_name).lt(
                value
            )
            Log_KeyConditionExpression += " & Key({}).lt({})".format(
                attribute_name, value
            )
            ascending = False
        elif condition == "!=":
            val_rng = " "
            if isinstance(value, bool):
                val_rng = False
            elif isinstance(value, int) or isinstance(value, float):
                val_rng = -4503599627370545

            KeyConditionExpression = KeyConditionExpression & Key(attribute_name).gte(
                val_rng
            )
            Log_KeyConditionExpression += " & Key({}).gte({})".format(
                attribute_name, val_rng
            )

            # != condition overwrites filter
            filter = {"conditions": {"eq": value}, "not": True, "key": attribute_name}

    kwargs = {
        "KeyConditionExpression": KeyConditionExpression,
        "ScanIndexForward": params["ascending"]
        if "ascending" in params and params["ascending"] != None
        else ascending,
    }

    _filterExpression = ""
    if filter and "conditions" in filter:
        if not isinstance(filter["conditions"], dict):
            raise Exception("filter conditions should be dict.")

        # set filter (filter expression) https://boto3.amazonaws.com/v1/documentation/api/latest/reference/customizations/dynamodb.html#dynamodb-conditions
        if "not" in filter and filter["not"]:
            for c in filter["conditions"]:
                if c in ["exists", "not_exists"]:
                    cond = (
                        Attr(filter["key"]).not_exists()
                        if c == "exists"
                        else Attr(filter["key"]).exists()
                    )

                else:
                    att = getattr(Attr(filter["key"]), c)
                    cond = Not(att(filter["conditions"][c]))

                kwargs["FilterExpression"] = (
                    cond
                    if not "FilterExpression" in kwargs
                    else kwargs["FilterExpression"] & cond
                )

                _filterExpression += "Not(attr({}).{}({}))(&)".format(
                    filter["key"], c, filter["conditions"][c]
                )
        else:
            for c in filter["conditions"]:
                if c in ["exists", "not_exists"]:
                    cond = (
                        Attr(filter["key"]).exists()
                        if c == "exists"
                        else Attr(filter["key"]).not_exists()
                    )

                else:
                    att = getattr(Attr(filter["key"]), c)
                    cond = att(filter["conditions"][c])

                kwargs["FilterExpression"] = (
                    cond
                    if not "FilterExpression" in kwargs
                    else kwargs["FilterExpression"] & cond
                )

                _filterExpression += "attr({}).{}({})(&)".format(
                    filter["key"], c, filter["conditions"][c]
                )

    if isinstance(primaryIndex, list):
        # set gsi index name
        kwargs["IndexName"] = "-".join(primaryIndex)

    elif not primaryIndex:
        # is local secondary index or single hash key that are not on primary index
        kwargs["IndexName"] = attribute_name

    elif isinstance(primaryIndex, str):
        kwargs["IndexName"] = primaryIndex

    if projection:
        # setup projection
        projection_expression = ""
        kwargs["ExpressionAttributeNames"] = {}

        for c in projection:
            column_name = "#{}".format(c)

            if not column_name in kwargs["ExpressionAttributeNames"]:
                kwargs["ExpressionAttributeNames"][column_name] = c
                projection_expression += "{},".format(column_name)

        projection_expression = projection_expression[:-1]
        kwargs["ProjectionExpression"] = projection_expression

    if startKey:
        kwargs["ExclusiveStartKey"] = startKey

    if limit:
        kwargs["Limit"] = limit

    ###############################################################################################
    # log

    print("\n{}[QUERY START]{}\n".format(sep, sep))

    _kwarg = {
        "KeyConditionExpression": Log_KeyConditionExpression,
        "FilterExpression": _filterExpression,
    }

    for k in kwargs:
        if k != "KeyConditionExpression" and k != "FilterExpression":
            _kwarg[k] = kwargs[k]

    pprint(_kwarg, width=1024, depth=4)

    print("\n{}[QUERY END]{}\n".format(sep, sep))

    ###############################################################################################
    # fetch records

    def get_records(kwargs, search_contains, recurse_counter=0):
        r = table.query(**kwargs)

        # search for contains. !cost warning!
        if (
            search_contains
            and not r["Items"]
            and "LastEvaluatedKey" in r
            and r["LastEvaluatedKey"]
        ):
            # recurse if there is no record
            kwargs["ExclusiveStartKey"] = result["LastEvaluatedKey"]

            if recurse_counter < 3:
                # recurse 3 times if there is no item
                return get_records(
                    kwargs, search_contains, recurse_counter=recurse_counter + 1
                )

        return r

    result = {"Items": []}

    try:
        result = get_records(kwargs, True if filter else False)

    except botocore.exceptions.ClientError as error:
        if error.response["Error"]["Code"] == "ValidationException":
            if (
                "The provided starting key does not match the range key predicate"
                in error.response["Error"]["Message"]
            ):
                pass
            else:
                raise error

        else:
            raise error

    print("\n{}[QUERY RESULT]{}\n".format(sep, sep))
    pprint(result, width=1024, depth=4)
    print("\n{}[QUERY RESULT]{}\n".format(sep, sep))

    if normalize and result["Items"]:
        normalizer(result["Items"], normalize if callable(normalize) else None)

    if "LastEvaluatedKey" in result:
        normalizer(result["LastEvaluatedKey"])
    else:
        result["LastEvaluatedKey"] = None

    return result


def get(params, normalize=False):
    """

    Get record from database.

    Use example:
        get({
            "table": boto3.resource('dynamodb').Table('table'),
            "key": {
                "hash": "hash key",
                "range": "range key"
            } | {}[],
            "projection": ['attr1', 'attr2'],
            "order": "key range"
        })

    """

    batch_keys = None

    print("\n{}[GET PARAMS START]{}\n".format(sep, sep))
    pprint(params, width=1024, depth=4)
    print("\n{}[GET PARAMS END]{}\n".format(sep, sep))

    try:
        # required params
        table = prepare_table(params["table"])
        key = params["key"]

        if isinstance(key, list):
            batch_keys = key

    except:
        raise Exception("get: required parameter is missing.")

    if not batch_keys and not isinstance(key, dict):
        raise Exception("get: key needs to be a dictionary.")

    kwarg = {"Key": key}

    if (
        "projection" in params
        and params["projection"]
        and isinstance(params["projection"], list)
    ):
        kwarg["ProjectionExpression"] = ""
        kwarg["ExpressionAttributeNames"] = {}

        for p in params["projection"]:
            exp_name = "#{}".format(p)
            kwarg["ProjectionExpression"] += "{},".format(exp_name)
            kwarg["ExpressionAttributeNames"][exp_name] = p

        kwarg["ProjectionExpression"] = kwarg["ProjectionExpression"][:-1]

    print("\n{}[GET START]{}\n".format(sep, sep))
    print(kwarg)
    print("\n{}[GET END]{}\n".format(sep, sep))

    if batch_keys:
        # batch get
        split_batch = list(chunks(batch_keys, 100))

        result = {"Items": [], "LastEvaluatedKey": None}

        order_key = []
        for b in split_batch:
            # b = 100 batch

            p = {"Keys": b}  # list

            for i in b:
                # i = each Key
                if "order" in params and params["order"]:
                    order_key.append(i[params["order"]])

                for ik in i:
                    if isinstance(i[ik], float):
                        i[ik] = decimal.Decimal(str(i[ik]))

            if "ExpressionAttributeNames" in kwarg:
                p["ExpressionAttributeNames"] = kwarg["ExpressionAttributeNames"]

            if "ProjectionExpression" in kwarg:
                p["ProjectionExpression"] = kwarg["ProjectionExpression"]

            def get_batch(request_items, tbl_obj):
                # get table region from table name
                # [us31 | short region]-skapi-[table name]-[random string]

                response = db.batch_get_item(RequestItems=request_items)

                batch_result = {
                    "Items": normalizer(response["Responses"][tbl_obj.name], normalize if callable(normalize) else None)
                    if normalize
                    else response["Responses"][tbl_obj.name],
                    "LastEvaluatedKey": None,
                }

                if (
                    "UnprocessedKeys" in response["Responses"]
                    and tbl_obj.name in response["Responses"]["UnprocessedKeys"]
                    and "Keys" in response["Responses"]["UnprocessedKeys"][tbl_obj.name]
                    and len(
                        response["Responses"]["UnprocessedKeys"][tbl_obj.name]["Keys"]
                    )
                ):
                    # recurse to fetch more unprocessed keys
                    rec = get_batch(
                        response["Responses"]["UnprocessedKeys"],
                        tbl_obj,
                        normalize,
                        dynamodb[tbl_reg],
                    )
                    batch_result["Items"].extend(rec["Items"])

                return batch_result

            bat = get_batch({table.name: p}, table)

            result["Items"].extend(bat["Items"])

        # order batch get response
        if "order" in params and params["order"]:
            for r in result["Items"]:
                # replace order key array with actual fetched item
                order_key[order_key.index(r[params["order"]])] = r

            result["Items"] = order_key

        return result

    for k in kwarg["Key"]:
        if isinstance(kwarg["Key"][k], float):
            kwarg["Key"][k] = decimal.Decimal(str(kwarg["Key"][k]))

    result = table.get_item(**kwarg)

    if "Item" in result and result["Item"]:
        if normalize:
            normalizer(result["Item"], normalize if callable(normalize) else None)

        return result
    else:
        return {"Item": {}}


def put(params, normalize=True):
    """

    Uploads record to database

    put({
        "table": boto3.resource('dynamodb').Table('table'),
        "item": { "attribute_name": value },
        "return": True,
        "not_exists": "key_name"
    })

    """
    print("\n{}[PUT PARAMS START]{}\n".format(sep, sep))
    pprint(params, depth=4, width=1024)
    print("\n{}[PUT PARAMS END]{}\n".format(sep, sep))

    try:
        # required params
        table = prepare_table(params["table"])
        item = params["item"]

    except:
        raise Exception("put: required parameter is missing")

    def float_to_decimal(i):
        for k in i:
            if isinstance(i[k], float):
                i[k] = decimal.Decimal(str(i[k]))

    if isinstance(item, list):
        for c in list(chunks(item, 25)):
            with table.batch_writer() as batch:
                for i in c:
                    float_to_decimal(i)
                    batch.put_item(Item=i)

        return "BATCH_WRITE_COMPLETE"

    else:
        float_to_decimal(item)
        ReturnValues = "NONE"
        if "return" in params and params["return"]:
            ReturnValues = "ALL_OLD"

        put_params = {"ReturnValues": ReturnValues, "Item": item}

        if "not_exists" in params:
            put_params["ConditionExpression"] = Attr(params["not_exists"]).not_exists()

        try:
            print("-- put_params --")
            pprint(put_params)
            print("--")

            result = table.put_item(**put_params)

        except botocore.exceptions.ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise Exception("EXISTS")
            else:
                raise e

        if "return" in params and params["return"]:
            result["Item"] = {}
            if "Attributes" in result:
                result["Item"] = result["Attributes"]
                del result["Attributes"]
                if normalize:
                    normalizer(
                        result["Item"], normalize if callable(normalize) else None
                    )
            else:
                result["Item"] = normalizer(params["item"], normalize if callable(normalize) else None)

        return result


def delete(params):
    """
    Uploads record to database

    delete({
        "table": boto3.resource('dynamodb').Table('table'),
        "key": { "attribute_name": value } | { "attribute_name": value }[],
        "condition": {
            "key": "key name",
            "eq": "value"
        },
        'bypass_conditional_error': False
        # !! condition expression does not work on batch delete !!
    })
    """
    print("\n{}[DELETE PARAMS START]{}\n".format(sep, sep))
    pprint(params, depth=4, width=1024)
    print("\n{}[DELETE PARAMS END]{}\n".format(sep, sep))

    try:
        # required params
        table = prepare_table(params["table"])
        key = params["key"]

    except:
        raise Exception("delete: required parameter is missing")

    if isinstance(key, list):
        for c in list(chunks(key, 25)):
            with table.batch_writer() as batch:
                for i in c:
                    q = {"Key": i}

                    if "condition" in params:
                        raise Exception(
                            "delete: batch delete cannot have conditional expression."
                        )

                    batch.delete_item(**q)

        return "BATCH_DELETE_COMPLETE"

    else:
        q = {"Key": key}

        condition_expression = None
        if "condition" in params:
            att = Attr(params["condition"]["key"])
            for c in params["condition"]:
                if c != "key":
                    condition_expression = getattr(att, c)(params["condition"][c])
                    break

        if condition_expression:
            q["ConditionExpression"] = condition_expression

        try:
            return table.delete_item(**q)

        except botocore.exceptions.ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                if params.get("bypass_conditional_error", False):
                    return "CONDITION_FAILED"

                raise Exception("CONDITION_FAILED")
            else:
                raise e


def update(params, normalize=False):
    """

    Updates record to database

    update({
        "table": boto3.resource('dynamodb').Table('table'),
        "key": { "hash": "hash value", "range": "range value" },
        "item": { "attribute_name": value | '*add ["set_value"]' | '*add 1' }, # *add *sub *inv
        "exists": "attribute name" (*attribute name for not exists), ($attribute name > json_value),
        "return": "OLD" | "NEW" | None,
        "remove": ["Attribute", "Attribute*0(index number)", "{setcolumn#setvalue}"] # removes list/set item
        "bypass_conditional_error": False,
    })

    """
    print("\n{}[UPDATE PARAMS START]{}\n".format(sep, sep))
    pprint(params, depth=4, width=1024)
    print("\n{}[UPDATE PARAMS END]{}\n".format(sep, sep))

    item = params.get("item", {})
    try:
        # required params
        table = prepare_table(params["table"])
        key = params["key"]

    except:
        raise Exception("update: required parameter is missing")

    for k in key:
        if isinstance(key[k], float):
            key[k] = decimal.Decimal(str(key[k]))

    query = {
        "Key": key,
        "ExpressionAttributeNames": {},
        "UpdateExpression": "",
        "ExpressionAttributeValues": {},
    }

    bypass_conditional_error = False

    if params.get("exists"):
        if params["exists"][0] == "*":
            query["ConditionExpression"] = Attr(params["exists"][1:]).not_exists()

        elif params["exists"][0] == "$":
            q = params["exists"][1:].split(" ")
            att = Attr(q[0])
            val = json.loads(q[2])

            if q[1] == "=":
                query["ConditionExpression"] = att.eq(val)

            elif q[1] == ">":
                query["ConditionExpression"] = att.gt(val)

            elif q[1] == "<":
                query["ConditionExpression"] = att.lt(val)

            elif q[1] == ">=":
                query["ConditionExpression"] = att.gte(val)

            elif q[1] == "<=":
                query["ConditionExpression"] = att.lte(val)

            elif q[1] == "!=":
                query["ConditionExpression"] = att.ne(val)

        else:
            query["ConditionExpression"] = Attr(params["exists"]).exists()

        bypass_conditional_error = params.get("bypass_conditional_error", False)

    returnValues = "NONE"

    if "return" in params:
        if params["return"] == "OLD":
            returnValues = "ALL_OLD"

        elif params["return"] == "NEW":
            returnValues = "ALL_NEW"

    to_invert = []
    to_add = []
    to_set = []
    to_del = []

    # write update expressions
    for att in list(item):
        if att in key:
            del item[att]
            continue

        query["ExpressionAttributeNames"]["#" + att] = att

        if isinstance(item[att], str):
            if "*pass" == item[att]:
                continue

            elif "*add" in item[att]:
                add_val = item[att].replace("*add ", "")

                if not add_val:
                    continue

                if add_val.lstrip("-").replace(".", "", 1).isdigit():
                    # add numbers if integer
                    if "." in add_val:
                        add_val = decimal.Decimal(add_val)
                    else:
                        add_val = int(add_val)

                    query["ExpressionAttributeValues"][f":add_{att}"] = add_val
                    to_set.append(
                        f"#{att} = if_not_exists(#{att}, :num_zero) + :add_{att}"
                    )
                    query["ExpressionAttributeValues"][":num_zero"] = 0
                else:
                    # add list if string | list
                    try:
                        add_val = json.loads(add_val)
                    except json.decoder.JSONDecodeError as err:
                        add_val = [add_val]

                    query["ExpressionAttributeValues"][f":add_{att}"] = set(add_val)

                    to_add.append(f"#{att} :add_{att}")

            elif "*sub" in item[att]:
                sub_val = item[att].replace("*sub ", "")
                if not sub_val:
                    continue

                if sub_val.lstrip("-").replace(".", "", 1).isdigit():
                    # subtract if number
                    if "." in sub_val:
                        sub_val = decimal.Decimal(sub_val)
                    else:
                        sub_val = int(sub_val)

                    query["ExpressionAttributeValues"][f":sub_{att}"] = sub_val

                    # if not exists, set to 0
                    to_set.append(
                        f"#{att} = if_not_exists(#{att}, :sub_{att}) - :sub_{att}"
                    )
                else:
                    # remove set item if string
                    try:
                        sub_val = json.loads(sub_val)
                    except json.decoder.JSONDecodeError as err:
                        sub_val = [sub_val]

                    query["ExpressionAttributeValues"][f":sub_{att}"] = set(sub_val)

                    to_del.append(f"#{att} :sub_{att}")

            elif "*inv" == item[att]:
                # applies invert only if attribute exists.
                del query["ExpressionAttributeNames"]["#" + att]

                # list attributes to invert
                to_invert.append(att)

            else:
                to_set.append(f"#{att} = :{att}")
                query["ExpressionAttributeValues"][f":{att}"] = item[att]

        else:
            if isinstance(item[att], float):
                item[att] = decimal.Decimal(str(item[att]))

            to_set.append(f"#{att} = :{att}")
            query["ExpressionAttributeValues"][":{}".format(att)] = item[att]

    def remove_comma_at_end():
        if query["UpdateExpression"] and query["UpdateExpression"][-1] == ",":
            query["UpdateExpression"] = query["UpdateExpression"][:-1]

    if to_set:
        query["UpdateExpression"] += "SET " + ", ".join(to_set) + ","

    if to_invert:
        get_invert_att = get(
            {"table": params["table"], "key": params["key"], "projection": to_invert},
            True,
        )["Item"]

        if get_invert_att:
            for i in get_invert_att:
                if i in to_invert and (
                    isinstance(get_invert_att[i], int)
                    or isinstance(get_invert_att[i], float)
                ):
                    if not to_set:
                        query["UpdateExpression"] += "SET"

                    # apply attribute invert
                    query["ExpressionAttributeNames"]["#" + i] = i
                    query["UpdateExpression"] += " #{} = :inv_{},".format(i, i)
                    query["ExpressionAttributeValues"][":inv_{}".format(i)] = (
                        get_invert_att[i] * -1
                    )

    if "remove" in params and params["remove"]:

        def has_remove():
            remove_comma_at_end()
            query["UpdateExpression"] += (
                " REMOVE" if query["UpdateExpression"] else "REMOVE"
            )

        run_remove = False
        delete_set = {}
        
        if isinstance(params["remove"], str):
            params["remove"] = [params["remove"]]

        for r in params["remove"]:
            if "{" in r[0] and "}" in r[-1]:
                # {setcolumn#setvalue}
                target = r[1:-1]
                target = target.split("#")

                if len(target) < 2:
                    continue

                att = target[0]
                exp = target[1]

                if att in delete_set:
                    delete_set[att].append(exp)
                else:
                    delete_set[att] = [exp]

            else:
                if not run_remove:
                    has_remove()
                    run_remove = True

                target = r.split("*")
                att = target[0]
                idx = target[1] if len(target) == 2 else None
                exp = att + (f"[{idx}]" if idx else "")
                query["ExpressionAttributeNames"]["#" + att] = exp
                query["UpdateExpression"] += f" #{att},"

        if delete_set:
            remove_comma_at_end()
            query["UpdateExpression"] += (
                " DELETE" if query["UpdateExpression"] else "DELETE"
            )

            for att in delete_set:
                query["ExpressionAttributeNames"]["#" + att] = att
                query["UpdateExpression"] += f" #{att} :{att},"
                query["ExpressionAttributeValues"][f":{att}"] = set(delete_set[att])

    if to_add:
        remove_comma_at_end()
        query["UpdateExpression"] += (
            (" ADD " if query["UpdateExpression"] else "ADD ") + ", ".join(to_add) + ","
        )

    if to_del:
        remove_comma_at_end()
        query["UpdateExpression"] += (
            (" DELETE " if query["UpdateExpression"] else "DELETE ")
            + ", ".join(to_del)
            + ","
        )

    remove_comma_at_end()
    query["ReturnValues"] = returnValues

    key_to_remove = []
    for k in query:
        if not query[k]:
            key_to_remove.append(k)

    for k in key_to_remove:
        del query[k]

    if not query["UpdateExpression"]:
        raise Exception("NOTHING_TO_UPDATE")

    query["UpdateExpression"] = query["UpdateExpression"].lstrip().rstrip()

    print("\n{}[UPDATE QUERY START]{}\n".format(sep, sep))
    pprint(query, depth=4, width=1024)
    print("\n{}[UPDATE QUERY END]{}\n".format(sep, sep))

    result = None

    try:
        result = table.update_item(**query)

    except botocore.exceptions.ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            if not bypass_conditional_error:
                if params["exists"][0] == "*":
                    raise Exception("EXISTS")

                elif params["exists"][0] == "$":
                    raise Exception("CONDITION_FAILED")

                else:
                    raise Exception("NOT_EXISTS")

        else:
            raise e

    if result:
        if "Attributes" in result:
            result["Item"] = result["Attributes"]
            del result["Attributes"]
            if normalize:
                normalizer(result["Item"], normalize if callable(normalize) else None)

    return result


def condition_converter(condition, CustomError=Exception):
    condition_convert = {
        "gt": ">",
        "gte": ">=",
        "eq": "=",
        "lt": "<",
        "lte": "<=",
        "ne": "!=",
    }

    if condition and isinstance(condition, str) and condition in valid_conditions:
        if condition in condition_convert:
            condition = condition_convert[condition]

    else:
        joined_valid_condition = ", ".join(valid_conditions)
        raise CustomError(
            f'INVALID_PARAMETER: allowed "condition" value: {joined_valid_condition}'
        )

    if condition in condition_convert:
        condition = condition_convert[condition]

    return condition
