# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /usr/src/app

# Copy the current directory contents into the container at /usr/src/app
COPY . .

# Install any dependencies
RUN pip install --no-cache-dir -r app/requirements.txt

# Make sure scripts are executable
RUN chmod +x scripts/*.sh

# Make port 8000 available to the world outside this container
EXPOSE 8000

# Run FastAPI using Uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
