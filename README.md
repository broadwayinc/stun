# UDP hole punching

This is a simple implementation of UDP hole punching using AWS Lambda and API Gateway.

# How To Run

Just open the **index.html** from your browser and see it in action.
All backend services are hosted on AWS.

# Test client API

You can test the API called from python script in /client folder.

```
$ python3 ./client/client_api.py
```

In this script, you can configure the token, roomId, client_port, and the stun server endpoint.

The API works as follows:
- Request to STUN server to get the public IP and port of the client.
- Make websocket connection to the server, Join the room of the roomId.
- Call http API to get list of users in the room.
- The websocket connection will be open and receive message whenever new user joins the room.

# How to deploy

If you want to deploy it yourself, follow the instructions below.

## Pre-Requisites

- Run **stun_server.py** in UDP port (application port is: 3478 but you can change it in the code) in your server.

- Configure your AWS CLI with your credentials.

- Install the following tools:
  - AWS CLI
  - SAM CLI
  - Python3

## Deploying AWS Resources

Run the following commands to deploy the application:
```
$ python3 deploy_script.py
```

## Hosting the website remotely

If you are working on remote servers, you can host the website remotely.

Install nodejs and use the following command to host the website:

```
$ npm i; npm run dev
```

Hosting will be done on port 3300.
You can change the port by modifying the **package.json** file.