# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory
WORKDIR /app

# Install system dependencies required by the shell script
RUN apt-get update && apt-get install -y \
    wget \
    git \
    curl \
    nix \
    dos2unix \
    tcl \
    tcllib \
    && rm -rf /var/lib/apt/lists/*

# Set up Nix environment
RUN mkdir -p /nix && chmod 777 /nix
ENV USER=root
ENV NIX_PATH=/root/.nix-defexpr/channels
ENV PATH=/root/.nix-profile/bin:/root/.nix-profile/sbin:$PATH

# Install Nix properly
RUN curl -L https://nixos.org/nix/install | sh && \
    . /root/.nix-profile/etc/profile.d/nix.sh && \
    nix-channel --update && \
    nix-env -iA nixpkgs.nix

# Source the Nix environment
SHELL ["/bin/bash", "-c"]

# Copy the shell script and Python code into the container
COPY process_openlane.sh /app/process_openlane.sh
COPY main.py /app/main.py
COPY spm /app/spm

# Convert script to Unix format (only if necessary)
RUN dos2unix /app/process_openlane.sh || true

# Ensure the shell script is executable
RUN chmod +x /app/process_openlane.sh

# Copy and install Python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Expose the port the app runs on
EXPOSE 5000

# Run the FastAPI application with Uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5000"]
