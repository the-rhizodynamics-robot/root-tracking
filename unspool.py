import os
import subprocess
import sys
import argparse

# Set up argument parser
parser = argparse.ArgumentParser(description='Run unspool_core.py with specified input and output directories.')
parser.add_argument('--input_dir', type=str, required=True, help='Path to input video directory')
parser.add_argument('--output_dir', type=str, required=True, help='Path to output directory for unspooled images')
parser.add_argument('--container', type=str, default='docker', choices=['docker', 'singularity'], 
                    help='Container runtime to use (docker or singularity)')
args = parser.parse_args()

input_dir = args.input_dir
output_dir = args.output_dir
container_type = args.container

# Ensure directories exist
os.makedirs(input_dir, exist_ok=True)
os.makedirs(output_dir, exist_ok=True)

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

    # Run the container with the unspooling script
    cmd = [
        "docker", "run", "--rm", "-it",
        "-v", f"{os.path.abspath(input_dir)}:/app/input",
        "-v", f"{os.path.abspath(output_dir)}:/app/output",
        image_name,
        "python", "/app/code/unspool_core.py",
        "--input_path", "/app/input",
        "--output_path", "/app/output"
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
    
    # Run the container with the unspooling script
    cmd = [
        "singularity", "exec",
        "--bind", f"{os.path.abspath(input_dir)}:/app/input",
        "--bind", f"{os.path.abspath(output_dir)}:/app/output",
        singularity_file,
        "python", "/app/code/unspool_core.py",
        "--input_path", "/app/input",
        "--output_path", "/app/output"
    ]

print(f"Running unspool_stabilize_core.py with input from {input_dir} and output to {output_dir}")
subprocess.run(cmd)
print("Unspooling process completed.")