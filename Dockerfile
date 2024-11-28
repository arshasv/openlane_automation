# Use an official Python runtime as a parent image
FROM python:3.9-slim


# Set the working directory
WORKDIR /app

# Install system dependencies required by the shell script
RUN apt-get update && apt-get install -y \
    wget \
    git \
    nix \
    && rm -rf /var/lib/apt/lists/*

# Copy the shell script and Python code into the container
COPY process_openlane.sh /app/process_openlane.sh
COPY main.py /app/main.py

# Install Python dependencies (FastAPI, Uvicorn)
# Copy and install Python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir fastapi uvicorn

# Ensure the shell script is executable
RUN chmod +x /app/process_openlane.sh

# Expose the port the app runs on
EXPOSE 8000

# Run the FastAPI application with Uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
