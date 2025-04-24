import json
import boto3
import botocore
import sys
import traceback
from IPython.display import display, Markdown
import argparse
import os

def read_file_content(file_path):
    """Read and return the content of a file."""
    try:
        with open(file_path, 'r') as file:
            return file.read()
    except IOError as e:
        print(f"Error reading file {file_path}: {e}")
        return None

def write_file_content(file_path, content):
    """Write content to a file."""
    try:
        with open(file_path, 'w') as file:
            file.write(content)
        print(f"Successfully updated {file_path}")
    except IOError as e:
        print(f"Error writing to file {file_path}: {e}")

def invoke_bedrock_model(bedrock, model_id, prompt):
    """Invoke Bedrock model and return the response."""
    try:
        request_body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1000,
            "messages": [
                {
                    "role": "user", 
                    "content": prompt
                }
            ]
        })

        response = bedrock.invoke_model(
            modelId=model_id,
            body=request_body,
            accept="application/json",
            contentType="application/json"
        )

        response_body = json.loads(response.get('body').read())
        
        extraction_strategies = [
            lambda rb: rb.get('content', [{}])[0].get('text'),
            lambda rb: rb.get('text'),
            lambda rb: rb.get('output')
        ]

        for strategy in extraction_strategies:
            try:
                claude_response = strategy(response_body)
                if claude_response:
                    return claude_response
            except Exception:
                continue

        return None

    except botocore.exceptions.ClientError as client_error:
        print(f" Client Error for {model_id}: {client_error}")
        error_code = client_error.response.get('Error', {}).get('Code')
        error_message = client_error.response.get('Error', {}).get('Message')
        print(f"Error Code: {error_code}")
        print(f"Error Message: {error_message}")
        return None

    except Exception as e:
        print(f" Unexpected Error: {e}")
        traceback.print_exc()
        return None

def read_json_file(file_path):
    """Read and return the content of a JSON file."""
    try:
        with open(file_path, 'r') as file:
            return json.load(file)
    except IOError as e:
        print(f"Error reading JSON file {file_path}: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON from file {file_path}: {e}")
        return None

def parse_sonarqube_issues(sonarqube_json):
    """Parse SonarQube JSON and return issues by filename."""
    issues_by_file = {}
    for file_entry in sonarqube_json:
        filename = file_entry['fileName']
        issues = file_entry['issues']
        issues_by_file[filename] = issues
    return issues_by_file

def extract_code_from_response(response):
    """Extract the code block from the model's response."""
    start_marker = "```go"
    end_marker = "```"
    start_index = response.find(start_marker)
    if start_index != -1:
        start_index += len(start_marker)
        end_index = response.find(end_marker, start_index)
        if end_index != -1:
            return response[start_index:end_index].strip()
    return None

def process_files_in_folder(folder_path, sonarqube_json):
    """Process all files in the given folder."""
    try:
        session = boto3.Session(region_name='us-east-1')
        bedrock = session.client('bedrock-runtime')
    except Exception as e:
        print(f" Client Creation Error: {e}")
        traceback.print_exc()
        return

    model_id = "anthropic.claude-3-5-sonnet-20240620-v1:0"
    issues_by_file = parse_sonarqube_issues(sonarqube_json)

    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        if os.path.isfile(file_path):
            print(f"\nProcessing file: {filename}")
            file_content = read_file_content(file_path)
            if file_content is not None:
                file_issues = issues_by_file.get(filename, [])
                if not file_issues:
                    print(f"No SonarQube issues for {filename}, skipping.")
                    continue

                issues_text = "\n".join([f"- Line {issue['startLine']}-{issue['endLine']}: {issue['message']}" for issue in file_issues])
                
                prompt = f"""The following file has some issues reported by SonarQube. Apply fixes for all issues and return the updated file. Add brief comments where changes were made.

File: {filename}

SonarQube Issues:
{issues_text}

File Content:
<text>
{file_content}
</text>

Please provide the corrected version of the file with fixes applied and comments added. Wrap the entire corrected code in a code block using ```go and ``` markers . Make sure to add these markers"""
                
                response = invoke_bedrock_model(bedrock, model_id, prompt)
                print(f"response {response}")
                if response:
                    updated_code = extract_code_from_response(response)
                    if updated_code:
                        write_file_content(file_path, updated_code)
                    else:
                        print(f"Failed to extract updated code for {filename}")
                else:
                    print(f"No response extracted for {filename}")
            else:
                print(f"Skipping {filename} due to read error")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process files in a folder using Bedrock Model")
    parser.add_argument("-d", "--directory", required=True, help="Path to the directory containing source files")
    parser.add_argument("-j", "--json", required=True, help="Path to the SonarQube JSON file")
    args = parser.parse_args()

    # SonarQube JSON (you can load this from a file if needed)
    sonarqube_json = read_json_file(args.json)

    process_files_in_folder(args.directory, sonarqube_json)
