import os
import subprocess
import webbrowser
import sys
import argparse

# Set up argument parser
parser = argparse.ArgumentParser(description='Run JupyterLab with specified data and results directories.')
parser.add_argument('--data_dir', type=str, required=True, help='Path to image data directory')
parser.add_argument('--results_dir', type=str, required=True, help='Path to save results directory')
parser.add_argument('--container', type=str, default='singularity', choices=['docker', 'singularity'], 
                    help='Container runtime to use (docker or singularity)')
args = parser.parse_args()

data_dir = args.data_dir
results_dir = args.results_dir
container_type = args.container


# Ensure directories exist
os.makedirs(data_dir, exist_ok=True)
os.makedirs(results_dir, exist_ok=True)

# Container image settings
image_name = "ghcr.io/the-rhizodynamics-robot/root-tracking-env:latest"

if container_type == "docker":
    # Pull the latest image from GitHub Container Registry
    print("Pulling latest Docker image...")
    pull_cmd = ["docker", "pull", image_name]
    pull_result = subprocess.run(pull_cmd, capture_output=True, text=True)
    if pull_result.returncode != 0:
        print(f"Error pulling Docker image: {pull_result.stderr}")
        sys.exit(1)
    print("Docker image pulled successfully.")

    # Run the Jupyter container with environment variables for data and results paths
    cmd = [
        "docker", "run", "--rm", "-it", "-p", "8888:8888",
        "-v", f"{os.path.abspath(data_dir)}:/app/data",
        "-v", f"{os.path.abspath(results_dir)}:/app/results",
        "-e", f"DATA_DIR={os.path.abspath(data_dir)}",
        "-e", f"RESULTS_DIR={os.path.abspath(results_dir)}",
        image_name,
        "jupyter", "lab", "--ip=0.0.0.0", "--port=8888", "--no-browser", "--allow-root"
    ]
    
elif container_type == "singularity":
    # Pull the latest image from GitHub Container Registry
    print("Pulling latest Singularity image...")
    singularity_image = f"docker://{image_name}"
    singularity_file = "root-tracking-env_latest.sif"
    
    pull_cmd = ["singularity", "pull", singularity_file, singularity_image]
    pull_result = subprocess.run(pull_cmd, capture_output=True, text=True)
    if pull_result.returncode != 0:
        print(f"Error pulling Singularity image: {pull_result.stderr}")
        sys.exit(1)
    print("Singularity image pulled successfully.")
    
    # Run the Jupyter container with environment variables for data and results paths
    cmd = [
        "singularity", "exec",
        "--bind", f"{os.path.abspath(data_dir)}:/app/data",
        "--bind", f"{os.path.abspath(results_dir)}:/app/results",
        f"--env=DATA_DIR={os.path.abspath(data_dir)}",
        f"--env=RESULTS_DIR={os.path.abspath(results_dir)}",
        singularity_file,
        "jupyter", "lab", "--ip=0.0.0.0", "--port=8888", "--no-browser"
    ]

subprocess.run(cmd)

# Open browser automatically
webbrowser.open("http://localhost:8888")