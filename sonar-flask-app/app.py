from flask import Flask, request, jsonify
from urllib.parse import unquote
import subprocess
import os

def run_command(command, env=None, capture_output=False):
    """Run a shell command and return its output."""
    result = subprocess.run(
        command, 
        shell=True, 
        env=env, 
        stdout=subprocess.PIPE if capture_output else None,
        stderr=subprocess.PIPE if capture_output else None, 
        text=True
    )
    if capture_output:
        return result
    
    if result.returncode != 0:
        print(f"Error running command: {command}")
        print(result.stderr)
    else:
        print(result.stdout)
    return result

app = Flask(__name__)

@app.route('/fix-repo', methods=['GET'])
def analyze_repo():
    repo_url = request.args.get('repo')
    if not repo_url:
        return jsonify({"error": "Missing 'repo' parameter"}), 400
    print(f"Received repo encoded: {repo_url}")
    repo_url = unquote(repo_url)
    print(f"Received repo decoded: {repo_url}")
    
    result = run_command(f"python3 final1.py --repo_url git@github.com:aviral-jain06/sonarqube-hackathon.git", env=os.environ, capture_output=True)
    
    # Convert the CompletedProcess object to a JSON-serializable dictionary
    response_data = {
        "stdout": result.stdout,
        "stderr": result.stderr,
        "returncode": result.returncode,
        "status": "success" if result.returncode == 0 else "error"
    }
    
    return jsonify(response_data)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
