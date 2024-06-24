"""
What it is:
    AWS resource deployment script.
    This script is designed to automate the deployment process of AWS resources using AWS SAM CLI.

Pre-requisites:
    Install the AWS SAM CLI from https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli-install.html

The files in database_interface/ and ws/ will be deployed to AWS Lambda functions.

Run stun_server.py if you need a udp stun server.

- Baksa Gimm
"""

import os
import json
import os
import re
import json


def generate_yaml(get_nested_placeholders=False):
    """

    Generates yaml template from _template.yaml
    # Placeholder: # <_fileName>

    """

    if not os.path.exists("_template.yaml"):
        return

    print('generating template.yaml...')

    head_lines = []
    head_line_nums = []
    module_names = []
    indent_spaces = []
    replaced_content = []
    edited_module_source = []

    # Open and read the latest version of .yaml file
    with open(f"template.yaml" if get_nested_placeholders else f"_template.yaml", "r", encoding="UTF8") as f:
        source = f.readlines()
        for num, line in enumerate(source):
            stripped_line = list(line.lstrip())
            char_keys = ''.join(stripped_line[:5]) if get_nested_placeholders else ''.join(
                stripped_line[:3])
            # Identify the first three insertion key letters '#', ' ', '<'
            if ('# <__' if get_nested_placeholders else '# <') == char_keys:
                head_line_nums.append(num)
                head_lines.append(line)
                module_names.append(line.strip(' #<>\n'))
                indent_spaces.append(' ' * line.index('#'))

    module_nums = len(module_names)
    block = []
    i = 0

    for head_line, head_line_num, module_name, indent in zip(head_lines, head_line_nums, module_names, indent_spaces):
        if os.path.exists(f"{module_name}.yaml"):
            with open(f"{module_name}.yaml", "r", encoding="UTF8") as f:
                module_source = f.readlines()
                block.append(head_line)
                # Apply the indentation from the original template.yaml to each module_name.yaml files
                for line in module_source:
                    edited_module_source = indent + line
                    block.append(edited_module_source)
                block.append('\n')
                # Preserve the structure between # <headline>
                if i < module_nums - 1:
                    block.extend(
                        source[head_line_nums[i] + 1: head_line_nums[i + 1]])
                elif i == module_nums - 1:
                    block.extend(source[head_line_nums[i] + 1:])
                i += 1

    replaced_content = source[0:head_line_nums[0]] + block

    # Create the new version of .yaml file
    with open(f"template.yaml", "w", encoding="UTF8") as writer:
        writer.writelines(replaced_content)

    if not get_nested_placeholders:
        generate_yaml(True)

    print('...template.yaml generated')


def generate_json():
    if not os.path.exists("deploy.txt"):
        raise Exception('deploy.txt does not exists.')

    with open('deploy.txt', 'r', encoding="UTF8") as f:
        text = f.read().replace(' ', '').replace(
            '\\n', 'ÿ').replace(os.linesep, '')

        if "UPDATE_FAILED" in text:
            raise Exception('deployment failed.')

    # generate file
    anchor=["-START-", "-END-"]
    get_text = re.search(
        r"(?<={}).*?(?={})".format(anchor[0], anchor[1]), text)

    if get_text:
        endpoints = {}
        
        print('creating endpoints.json...')
        get_text = get_text.group(0)
        with open('endpoints.json', 'w', encoding="UTF8") as ns:
            text = get_text.replace('ÿ', os.linesep)
            ep = json.loads(text)
            ns.write(json.dumps(ep, indent=2))

            for k in ep:
                endpoints[k] = ep[k]

        with open('resource_list.json', 'w', encoding="UTF8") as ns:
            ns.write(json.dumps(endpoints, indent=2))

    else:
        print('generate_json(): no data to parse.')

    print('...complete')


# build yaml file

generate_yaml()

# run sam build

if os.system('sam build --cached') != 0:
    raise Exception('process terminated.')

if os.path.exists("samconfig.toml"):
    # deploy
    if os.system('sam deploy --capabilities CAPABILITY_NAMED_IAM | tee deploy.txt') != 0:
        raise Exception('process terminated.')
# init
elif os.system(
        'sam deploy --guided --capabilities CAPABILITY_NAMED_IAM | tee deploy.txt') != 0:
    raise Exception('process terminated.')

# generate json file

generate_json()
