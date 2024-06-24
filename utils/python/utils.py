import os
import time
import json


def send(code, data="", cors="*", cache=False, headers={}):
    """

    Sends out response.

    code : str
        Response status code.

    data : any
        Data to response.

    cors : str
        Cors url.

    cache: bool
        Respond with cache settings.

    headers: dict
        Respond headers to overwrite.

    """

    response = {"statusCode": code, "headers": {}}

    def access_control(code):
        response["statusCode"] = code
        response["headers"] |= {
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Allow-Methods": "*",
            "Access-Control-Allow-Origin": cors if code == 200 else "*",
        }

    if isinstance(data, Exception):
        # error response

        if isinstance(data, CustomError):
            access_control(400)

            data = json.dumps(data.err_obj)
            ContentType = 'application/json; charset="utf-8"'

        else:
            # is server error
            access_control(500)
            ContentType = 'text/plain; charset="utf-8"'
            data = os.environ["SOMETHING_WENT_WRONG"]

        response["headers"]["Content-Type"] = ContentType
        response["body"] = data

        print(response, "ERROR-RESPONSE")
        return response

    # set access control

    access_control(code)

    # redirect
    if code == 301:
        response["headers"]["Location"] = data
        print(response, "RESPONSE")
        return response

    response["headers"] |= headers

    # set cache
    if cache:
        if cache == True:
            # default cache to 10 minutes
            cache = 600

        if isinstance(cache, int):
            # respond with N seconds cache settings when int
            response["headers"][
                "Cache-Control"
            ] = f"Cache-Control: public, max-age={cache}, immutable"

    # respond as string
    if isinstance(data, str):
        response["headers"]["Content-Type"] = 'text/plains; charset="utf-8"'
        response["body"] = data
        print(response, "RESPONSE")
        return response

    # respond as json
    try:
        ContentType = 'application/json; charset="utf-8"'
        data = json.dumps(data)

    except Exception:
        # if not dumpable - ex) class instance, etc
        access_control(500)
        ContentType = 'text/plain; charset="utf-8"'
        data = "ERROR: Not parsable to JSON."

    response["headers"]["Content-Type"] = ContentType
    response["headers"] | headers
    response["body"] = data

    print(response, "RESPONSE")
    return response


class CustomError(Exception):
    # custom error will return message to user
    # custom error does not send error log to dev
    def __init__(self, message):
        if isinstance(message, str) and ":" in message:
            msg_break = message.split(":")
            msg_str = ":".join(msg_break[1:]).strip()
            msg_code = msg_break[0].strip()
            self.err_obj = {"code": msg_code, "message": msg_str}

        elif isinstance(message, dict):
            self.err_obj = {
                "code": message.get("code", "ERROR"),
                "message": message.get("message", "An error occured."),
            }

        else:
            self.err_obj = {"code": "ERROR", "message": str(message)}

        super().__init__(message)


def digest_event(event, data_type={}):
    headers = {k.lower(): v for k, v in event.get("headers", {}).items()}

    timestamp = round(time.time() * 1000)
    origin = headers.get("origin")
    content_type = headers.get("content-type")
    locale = headers.get("cloudfront-viewer-country")

    request_context = event.get("requestContext", {})
    # auth = request_context.get("authorizer", {}).get("claims")
    user_agent = request_context.get("identity", {}).get("userAgent")
    ip = request_context.get("identity", {}).get("sourceIp")

    method = None
    cors = "*"
    data = {}
    method = event["httpMethod"].lower()

    if method == "get":
        get_params = event.get("queryStringParameters")
        if get_params:
            for k in get_params:
                value = event["queryStringParameters"][k]

                try:
                    # parse if parseable json string
                    value = json.loads(value)
                except:
                    # gateway api seem to handle uri decoding...
                    pass

                data[k] = value

    elif method == "post":
        # only accept json for post
        if content_type == "application/json":
            try:
                parsed_body = json.loads(event["body"])

                if parsed_body and isinstance(parsed_body, dict):
                    data |= parsed_body

            except:
                raise CustomError(
                    os.environ["ERR_INVALID_REQUEST"] + ": Invalid content."
                )

        else:
            raise CustomError(
                os.environ["ERR_INVALID_REQUEST"] + ": Only 'application/json' allowed."
            )

    ###############################################################################################
    # check parameters

    if data_type:
        data = type_check(data, check=data_type)

    ###############################################################################################

    created_request = {
        "data": data,
        "locale": locale,
        "timestamp": timestamp,
        "origin": origin,
        "cors": cors,
        "method": method,
        "user_agent": user_agent,
        "ip": ip,
        "headers": headers,
    }

    print(created_request)

    return created_request


def type_check(data, check={}, _parent_key=""):
    """

    Request body checker.
    Bypass check if key data is None.

    check={
        'key_name1': type | [multiType],
        'key_name2': lambda x: 'conditional' if x == 'condition' else None,
        'key_name3': [int, str, list, dict, (value to match str/int/bool/None), lambda x='default': x]
        'key_name4': {
            'nested1': int
        },
        'key_name5': [{
            'nested1': int
        }, 'mixedStruct']
    }

    if the type is not mentioned, it will not be checked.

    """

    if callable(check) and not isinstance(check, type):
        return check(data)

    elif not check and isinstance(check, dict):
        # check is empty dict
        return data

    elif isinstance(check, dict):
        # run checks
        if not isinstance(data, dict):
            raise CustomError(
                os.environ["ERR_INVALID_PARAMETER"] + ": Data schema does not match."
            )

        for k in list(check):
            if k in data:
                data[k] = type_check(data[k], check=check[k], _parent_key=k)
            else:
                c = check[k]
                if not isinstance(c, type):
                    if callable(c):
                        data[k] = c()
                    elif (
                        isinstance(c, list)
                        and not isinstance(c[-1], type)
                        and callable(c[-1])
                    ):
                        data[k] = c[-1]()

    elif isinstance(data, list):
        has_match = False

        if isinstance(check, type) and check.__name__ == "list":
            has_match = True

        elif isinstance(check, list):
            for c in check:
                if isinstance(c, type) and isinstance(data, c):
                    # matches check = [list, ...]
                    has_match = True
                    break

        if not has_match:
            # matches each item in check list
            for k in range(len(data)):
                data[k] = type_check(data[k], check=check, _parent_key=_parent_key)

    elif isinstance(check, list):
        passed = False
        allowed_values = ""

        for c in check:
            if isinstance(c, str):
                allowed_values += '"{}" | '.format(c)
                if data == c:
                    passed = True
                    break
            elif c == None and data == None:
                passed = True
                break
            elif isinstance(c, type) and isinstance(data, c):
                passed = True
                break
            elif callable(c) and not isinstance(c, type):
                data = c(data)
                passed = True
            elif isinstance(c, dict):
                try:
                    type_check(data, c)
                    passed = True
                    break
                except:
                    pass

        if not passed:
            if allowed_values:
                raise CustomError(
                    os.environ["ERR_INVALID_PARAMETER"]
                    + ': "{}" is invalid in "{}". allowed values are: {}.'.format(
                        data, _parent_key, allowed_values[:-3]
                    )
                )
            else:
                raise CustomError(
                    os.environ["ERR_INVALID_PARAMETER"]
                    + ': Type "{}" is invalid in "{}".'.format(
                        type(data).__name__, _parent_key
                    )
                )

    elif (
        check == None
        and check != data
        or isinstance(check, type)
        and not isinstance(data, check)
    ):
        raise CustomError(
            os.environ["ERR_INVALID_PARAMETER"]
            + ': Type "{}" is invalid in "{}".'.format(type(data).__name__, _parent_key)
        )

    return data


def authenticate_token(token: str) -> dict:
    # do whatever with the token
    # for now, we will use the token as the user id

    if token:
        return {"user_id": token, "service": "".join(e for e in os.environ["SERVICE"] if e.isalnum())}
    
    else:
        raise CustomError(os.environ["ERR_INVALID_REQUEST"] + ": Invalid token.")
