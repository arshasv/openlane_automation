# Use an official Python runtime as a parent image
FROM python:3.11-slim


# Set the working directory
WORKDIR /app

# Install system dependencies required by the shell script
RUN apt-get update && apt-get install -y gcc \
    wget \
    git \
    curl \
    dos2unix \
    tcl \
    tcllib \
    zip \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create the nixbld group and user
RUN groupadd -g 30000 nixbld && \
    useradd -u 30000 -g nixbld -m nixbld

# Add the nixbld user to the nixbld group
RUN usermod -aG nixbld nixbld

# Create /nix directory and set permissions
RUN mkdir -p /nix && chmod 777 /nix

# Install Nix in single-user mode
ENV USER=root
ENV NIX_PATH=/root/.nix-defexpr/channels
ENV PATH=/root/.nix-profile/bin:/root/.nix-profile/sbin:$PATH

RUN curl -L https://nixos.org/nix/install | sh -s -- --no-daemon && \
    . /root/.nix-profile/etc/profile.d/nix.sh && \
    nix-channel --add https://nixos.org/channels/nixpkgs-unstable nixpkgs && \
    nix-channel --update && \
    nix-env -iA nixpkgs.nix

# Source the Nix environment
SHELL ["/bin/bash", "-c"]

# Copy the shell script and Python code into the container
COPY process_openlane.py /app/process_openlane.py
COPY main.py /app/main.py
COPY app.py /app/app.py
COPY config.py /app/config.py

# Convert script to Unix format (only if necessary)
RUN dos2unix /app/process_openlane.py || true

# Ensure the shell script is executable
RUN chmod +x /app/process_openlane.py

# Create required directories and fix ownership
RUN mkdir -p /app/openlane2 /app/designs && \
    chown -R root:root /app/openlane2 /app/designs

# Copy and install Python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Expose the port the app runs on
EXPOSE 5000

# Run the FastAPI application with Uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5000"]