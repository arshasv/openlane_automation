import subprocess
import os
import zipfile
import uuid
import pika
import re
import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv
import shutil

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# FastAPI app instance
app = FastAPI()

# Pydantic model for input validation
class VerilogRequest(BaseModel):
    blob_url: str

class UploadRequest(BaseModel):
    design_folder: str

# Constants for shell script and Azure Blob Storage
SCRIPT_PATH = "./process_openlane.sh"

# Azure Blob Storage details
AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
BLOB_CONTAINER_NAME = os.getenv("BLOB_CONTAINER_NAME")

# RabbitMQ connection details
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", 5672))
RABBITMQ_QUEUE = os.getenv("RABBITMQ_QUEUE", "verilog_queue")

# Function to publish messages to RabbitMQ
def publish_to_rabbitmq(message: dict):
    try:
        credentials = pika.PlainCredentials(os.getenv("RABBITMQ_USER"), os.getenv("RABBITMQ_PASSWORD"))
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=RABBITMQ_HOST, port=RABBITMQ_PORT, credentials=credentials)
        )
        channel = connection.channel()
        channel.queue_declare(queue=RABBITMQ_QUEUE, durable=True)

        channel.basic_publish(
            exchange="",
            routing_key=RABBITMQ_QUEUE,
            body=str(message),
            properties=pika.BasicProperties(delivery_mode=2)
        )
        connection.close()
        logging.info(f"Message published to RabbitMQ: {message}")
    except Exception as e:
        logging.error(f"RabbitMQ Connection Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to publish to RabbitMQ: {str(e)}")

# Function to execute the shell script
def run_shell_script(blob_url: str):
    try:
        os.environ['BLOB_URL'] = blob_url
        
        result = subprocess.run(
            ["bash", SCRIPT_PATH],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        if result.returncode != 0:
            error_message = f"Shell script failed: {result.stderr}"
            logging.error(error_message)
            raise Exception(error_message)

        # Extract design folder name from the script output
        match = re.search(r"design_(\d{8}_\d{6})", result.stdout)
        if not match:
            error_message = "Design folder name not found in the script output"
            logging.error(error_message)
            raise Exception(error_message)

        design_folder = f"design_{match.group(1)}"
        runs_path = f"openlane2/designs/{design_folder}/runs"

        # Check if the 'runs' directory exists
        if os.path.exists(runs_path):
            success_message = {
                "status": "success",
                "message": "OpenLane flow completed successfully",
                "output": f"OpenLane flow completed successfully for {design_folder}"
            }
            logging.info(success_message)
            publish_to_rabbitmq(success_message)
            return success_message
        else:
            error_message = f"OpenLane compilation failed: '{runs_path}' not found"
            logging.error(error_message)
            raise Exception(error_message)
    
    except Exception as e:
        error_response = {"status": "error", "message": "OpenLane execution failed", "error": str(e)}
        logging.error(error_response)
        publish_to_rabbitmq(error_response)
        raise HTTPException(status_code=500, detail=error_response)

# Function to zip a folder
def zip_folder(folder_path: str):
    try:
        zip_filename = f"{folder_path}.zip"
        with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, _, files in os.walk(folder_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, folder_path)
                    zipf.write(file_path, arcname)
        return zip_filename
    except Exception as e:
        logging.error(f"Failed to zip folder: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to zip folder: {str(e)}")

# Function to upload a file to Azure Blob Storage
def upload_to_azure_blob(file_path: str):
    try:
        blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
        blob_client = blob_service_client.get_blob_client(container=BLOB_CONTAINER_NAME, blob=os.path.basename(file_path))

        with open(file_path, "rb") as data:
            blob_client.upload_blob(data, overwrite=True)

        success_message = f"File uploaded to Azure Blob Storage: {blob_client.url}"
        logging.info(success_message)
        return success_message
    except Exception as e:
        logging.error(f"Failed to upload file to Azure Blob Storage: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to upload file to Azure Blob Storage: {str(e)}")

# API endpoint to trigger OpenLane process
@app.post("/run_openlane")
def run_openlane(request: VerilogRequest):
    return run_shell_script(request.blob_url)

# API endpoint to zip and upload a folder to Azure Blob Storage
@app.post("/upload_to_blob")
async def upload_to_blob(request: UploadRequest):
    try:
        design_folder_path = f"openlane2/designs/{request.design_folder}"
        if not os.path.exists(design_folder_path):
            error_message = f"Design folder not found: {design_folder_path}"
            logging.error(error_message)
            raise HTTPException(status_code=404, detail=error_message)

        zip_file_path = zip_folder(design_folder_path)
        blob_url = upload_to_azure_blob(zip_file_path)

        os.remove(zip_file_path)

        message = {
            "type": "blob_upload",
            "design_folder": request.design_folder,
            "blob_url": blob_url,
            "status": "uploaded"
        }
        logging.info(message)
        publish_to_rabbitmq(message)

        return {"message": "Folder zipped and uploaded successfully", "blob_url": blob_url}
    except HTTPException as e:
        raise e
    except Exception as e:
        logging.error(f"Failed to upload folder: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to upload folder: {str(e)}")
