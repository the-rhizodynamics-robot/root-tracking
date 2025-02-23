To do:

set up github/workflows

Move code to image.


docker run -it --rm -p 8888:8888 jupyterlab

draft python runner (webbrowser is built in). Maybe consider singularity?

import os
import subprocess
import webbrowser

# Ask user for data and results paths
data_dir = input("Enter path to image data (default: ./data): ") or "./data"
results_dir = input("Enter path to save results (default: ./results): ") or "./results"

# Ensure directories exist
os.makedirs(data_dir, exist_ok=True)
os.makedirs(results_dir, exist_ok=True)

# Run the Jupyter container
cmd = [
    "docker", "run", "--rm", "-it", "-p", "8888:8888",
    "-v", f"{os.path.abspath(data_dir)}:/app/data",
    "-v", f"{os.path.abspath(results_dir)}:/app/results",
    "my-jupyterlab",
    "jupyter", "lab", "--ip=0.0.0.0", "--port=8888", "--no-browser", "--allow-root"
]
subprocess.run(cmd)

# Open browser automatically
webbrowser.open("http://localhost:8888")

