from urllib import parse, request
import json


def get_users(room: str) -> list[str]:
    # Define the base URL
    url = "https://4b6zwxd0l4.execute-api.us-east-1.amazonaws.com/api/get-ws-group"

    # Define the query parameters as a dictionary
    params = {"room": room}

    # Encode the query parameters
    query_string = parse.urlencode(params)

    # Append the query string to the URL
    full_url = f"{url}?{query_string}"

    # Perform the GET request
    response = request.urlopen(full_url)

    # Read and print the response content
    content = response.read()
    data = json.loads(content.decode("utf-8"))

    uli = []
    for i in data["list"]:
        ip, port = i["cnd"].split(":")
        uid = i["uid"].split("#")[-1]
        uli.append([ip, port, uid])
        
    return data["list"]
