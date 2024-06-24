# UDP hole punching

This is a simple implementation of UDP hole punching using AWS Lambda and API Gateway.

Open the **index.html** from your browser and see it in action.

If you want to deploy it yourself, follow the instructions below.

## Pre-requisites

- Run **stun_server.py** in UDP port (application port is: 3478 but you can change it in the code) in your server.

- Configure your AWS CLI with your credentials.

- Install the following tools:
  - AWS CLI
  - SAM CLI
  - Python3

## Deploying the application

Run the following commands to deploy the application:
```
$ python3 deploy_script.py
```

While running the script, you will be asked to provide a stack name, AWS region, and a service name. The stack name is the name of the CloudFormation stack that will be created. The service name is the name of the service that will be created. The AWS region is the region where the stack will be created.

You can proceed with the default values except:
    
    GetGroup has no authentication. Is this okay? [y/N]: y

This is because the API Gateway does not have any authentication. You can choose to add authentication if you want.

Configuring SAM deploy
======================

    Looking for config file [samconfig.toml] :  Not found

    Setting default arguments for 'sam deploy'
    =========================================
    Stack Name [sam-app]: stun-punch
    AWS Region [us-east-1]: 
    Parameter ServiceName [stunpunch]: 
    #Shows you resources changes to be deployed and require a 'Y' to initiate deploy
    Confirm changes before deploy [y/N]: N
    #SAM needs permission to be able to create roles to connect to the resources in your template
    Allow SAM CLI IAM role creation [Y/n]: Y
    #Preserves the state of previously provisioned resources when an operation fails
    Disable rollback [y/N]: N
    GetGroup has no authentication. Is this okay? [y/N]: y

## Hosting the website remotely

If you are working on remote servers, you can host the website remotely.

Install nodejs and use the following command to host the website:

```
$ npm i; npm run dev
```

Hosting will be done on port 3300.
You can change the port by modifying the **package.json** file.