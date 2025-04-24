import os
import subprocess
import argparse
import sys
import time
from datetime import datetime

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

def setup_gh_authentication():
    """Set up GitHub CLI authentication."""
    # First check if already authenticated
    auth_status = run_command("gh auth status", capture_output=True)
    
    if auth_status.returncode == 0:
        print("GitHub CLI is already authenticated.")
        return True
        
    print("\nSetting up GitHub CLI authentication...")
    
    run_command("source ~/.bashrc", capture_output=True)
    
    # Check if GH_TOKEN environment variable is set
    gh_token = "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"
    
    if gh_token:
        # Use token from environment variable
        print("Using GH_TOKEN environment variable for authentication...")
        auth_result = run_command(f'echo "{gh_token}" | gh auth login --with-token', capture_output=True)
        if auth_result.returncode == 0:
            print("Successfully authenticated with GitHub using token.")
            return True
    
    # If no environment token or it failed, try interactive login
    print("No token found or token authentication failed.")
    print("Please set the GH_TOKEN environment variable before running this script:")
    print("export GH_TOKEN=your_personal_access_token")
    print("\nOr manually authenticate by running: gh auth login")
    
    # Ask if user wants to try interactive authentication
    response = input("\nWould you like to try interactive authentication now? (y/n): ").strip().lower()
    
    if response == 'y':
        print("\nStarting interactive GitHub authentication...")
        # Run interactive login
        subprocess.run("gh auth login", shell=True)
        
        # Check if authentication was successful
        auth_check = run_command("gh auth status", capture_output=True)
        if auth_check.returncode == 0:
            print("Successfully authenticated with GitHub.")
            return True
        else:
            print("GitHub authentication failed or was cancelled.")
            return False
    else:
        print("Skipping GitHub authentication.")
        return False

def start_ssh_agent_and_add_key():
    # Start ssh-agent and get the environment variables it sets
    # Fixed escape sequences by using r-string
    agent_output = subprocess.check_output(r"eval \$(ssh-agent -s) && echo \$SSH_AUTH_SOCK && echo \$SSH_AGENT_PID", shell=True, text=True).splitlines()
    ssh_auth_sock = agent_output[0]
    ssh_agent_pid = agent_output[1]
    os.environ['SSH_AUTH_SOCK'] = ssh_auth_sock
    os.environ['SSH_AGENT_PID'] = ssh_agent_pid
    # Add the SSH key
    run_command("ssh-add ~/.ssh/id_rsa", env=os.environ)

def clone_repo(repo_url, local_path):
    """Clone the repository to the local path."""
    print(f"Cloning repository: {repo_url}")
    return run_command(f"git clone {repo_url} {local_path}", env=os.environ)

def run_sonar():
    """Run SonarQube analysis."""
    print("Running SonarQube analysis...")
    # Replace with your actual SonarQube command
    command = "sonar-scanner -Dsonar.projectKey=byte-brains -Dsonar.sources=. -Dsonar.host.url=http://ec2-3-88-49-28.compute-1.amazonaws.com:9001 -Dsonar.login=sqp_0731758e5c1e7d798bd7a53a1175afde225c2da8"
    return run_command(command, env=os.environ)

def run_scripty(local_path):
    """Run the testt.py file."""
    print("Running testt.py...")
    return run_command(f"python3 testt.py -d {local_path} -j temp.json", env=os.environ)

def create_pr(branch_name, base_branch, title):
    """Create a pull request."""
    return run_command(f"gh pr create --base {base_branch} --head {branch_name} --title \"{title}\" --body \"This PR updates the file.\"", env=os.environ)

def main(repo_url=None, local_path=None, base_branch="main"):
    # Set up GitHub authentication first
    gh_authenticated = setup_gh_authentication()
    # If no local path is provided, use a default name
    if local_path is None:
        # Extract repo name from URL for default local path
        repo_name = repo_url.split("/")[-1].replace(".git", "")
        local_path = f"{repo_name}_clone"
    
    # Clone the repository
    clone_repo(repo_url, local_path)
    run_scripty(local_path)
    os.chdir(local_path)

    # Run SonarQube analysis
    run_sonar()

    # Check for changes
    result = run_command("git status --porcelain",capture_output=True)
    if not result.stdout:
        print("No files were changed. Exiting.")
        return
    
    changed_files = result.stdout.splitlines()

    # Get the current branch name to return to later
    original_branch = run_command("git rev-parse --abbrev-ref HEAD", capture_output=True).stdout.strip()

    # Create a PR for each changed file
    for file_status in changed_files:
    # Get the file path from the git status output
    # The format is typically "XY filename" where X and Y are status codes
      file_path = file_status[3:] if file_status[0:2] == "??" else file_status[2:].strip()
    
    # Create a branch name based on the file name
      safe_filename = file_path.replace('/', '-').replace('.', '-')
      timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
      branch_name = f"update-{timestamp}-{safe_filename}"
    
    # Make sure we're starting from the base_branch each time
      run_command(f"git checkout {base_branch}")
    
    # Create and checkout new branch
      run_command(f"git checkout -b {branch_name}")
    
    # Stage only this specific file
      run_command(f"git add {file_path}")
    
    # Commit the file
      run_command(f"git commit -m \"Update {file_path}\"")
    
    # Push the branch
      run_command(f"git push origin {branch_name}")
    
    # Create PR
      pr_result = create_pr(branch_name, base_branch, f"Fix sonarqube issue in {file_path}")
      print(f"Created PR for {file_path}")
    
    # Return to the base branch for the next iteration
      run_command(f"git checkout {base_branch}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clone repo, run SonarQube, and create PRs")
    parser.add_argument("--repo_url", help="URL of the GitHub repository (default: current repo)")
    parser.add_argument("--local_path", help="Local path to clone the repository (default: reponame_clone)")
    parser.add_argument("--base_branch", default="main", help="Base branch for PRs (default: main)")

    # Parse only the known arguments
    args, unknown = parser.parse_known_args()
    
    if unknown:
        print(f"Warning: ignoring unknown arguments: {unknown}")

    # Call main with the parsed arguments
    main(args.repo_url, args.local_path, args.base_branch)
	
	
	 
