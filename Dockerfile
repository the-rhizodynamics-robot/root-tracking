FROM ghcr.io/the-rhizodynamics-robot/file-sorting-env@latest

# Install JupyterLab
RUN pip install --no-cache-dir jupyterlab

# Set working directory
WORKDIR /app

# Copy the notebooks and src directories into the container
COPY notebooks/ /app/notebooks/
COPY src/ /app/src/

# Expose JupyterLab port
EXPOSE 8888

# Start JupyterLab
CMD ["jupyter", "lab", "--ip=0.0.0.0", "--port=8888", "--no-browser", "--allow-root"]