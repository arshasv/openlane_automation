import subprocess
import os
import zipfile
import pika
import re
import logging
import time
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi import Request
from pydantic import BaseModel
from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv
from typing import List, Dict

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# FastAPI app instance
app = FastAPI()

# Pydantic models
class PinConfiguration(BaseModel):
    N: List[str]
    S: List[str]
    E: List[str]
    W: List[str]

class VerilogRequest(BaseModel):
    blob_url: str
    design_name: str
    clock_port: str
    clock_period: float
    die_area: str
    pin_configuration: PinConfiguration


class UploadRequest(BaseModel):
    design_folder: str

# Constants
SCRIPT_PATH = "./process_openlane.sh"

# Azure Blob Storage configuration
AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
BLOB_CONTAINER_NAME = os.getenv("BLOB_CONTAINER_NAME")

# RabbitMQ configuration
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", 5672))
RABBITMQ_QUEUE = os.getenv("RABBITMQ_QUEUE", "verilog_queue")
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "user")
RABBITMQ_PASSWORD = os.getenv("RABBITMQ_PASSWORD", "password")


# Function to publish messages to RabbitMQ
def publish_to_rabbitmq(message: dict):
    try:
        credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASSWORD)
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
        logging.error(f"Failed to send message to RabbitMQ: {str(e)}")


# Function to execute the shell script
def run_shell_script(request: VerilogRequest):
    try:
        os.environ['BLOB_URL'] = request.blob_url
        os.environ['DESIGN_NAME'] = request.design_name
        os.environ['CLOCK_PORT'] = request.clock_port
        os.environ['CLOCK_PERIOD'] = str(request.clock_period)
        os.environ['DIE_AREA'] = request.die_area

        # Set pin configuration as comma-separated values for each side
        os.environ['PINS_N'] = ','.join(request.pin_configuration.N)
        os.environ['PINS_S'] = ','.join(request.pin_configuration.S)
        os.environ['PINS_E'] = ','.join(request.pin_configuration.E)
        os.environ['PINS_W'] = ','.join(request.pin_configuration.W)

        # Log the command being executed
        command = [
            "bash", SCRIPT_PATH,
            request.design_name,
            str(request.clock_period),
            request.clock_port,
            ','.join(request.pin_configuration.N),
            ','.join(request.pin_configuration.S),
            ','.join(request.pin_configuration.E),
            ','.join(request.pin_configuration.W),
            request.die_area
        ]
        logging.info(f"Executing command: {' '.join(command)}")

        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        # Log the output for debugging
        logging.info(f"Shell script stdout: {result.stdout}")
        logging.error(f"Shell script stderr: {result.stderr}")

        if result.returncode != 0:
            raise Exception(f"Shell script failed: {result.stderr}")

        logging.info("Shell script completed successfully")
        return {
            "status": "success",
            "message": "OpenLane flow completed successfully",
        }

    except Exception as e:
        logging.error(f"OpenLane execution failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"OpenLane execution failed: {str(e)}")


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

        blob_url = f"https://{blob_client.account_name}.blob.core.windows.net/{BLOB_CONTAINER_NAME}/{os.path.basename(file_path)}"
        logging.info(f"File uploaded to Azure Blob Storage: {blob_url}")
        return blob_url
    except Exception as e:
        logging.error(f"Failed to upload file to Azure Blob Storage: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to upload file to Azure Blob Storage: {str(e)}")





# API endpoint to trigger OpenLane process
@app.post("/run_openlane")
def run_openlane(request: VerilogRequest):
    return run_shell_script(request)


# API endpoint to zip and upload a folder to Azure Blob Storage
@app.post("/upload_to_blob")
async def upload_to_blob(request: UploadRequest):
    try:
        design_folder_path = f"openlane2/designs/{request.design_folder}"
        if not os.path.exists(design_folder_path):
            logging.error(f"Design folder not found: {design_folder_path}")
            raise HTTPException(status_code=404, detail=f"Design folder not found: {design_folder_path}")

        zip_file_path = zip_folder(design_folder_path)
        blob_url = upload_to_azure_blob(zip_file_path)

        os.remove(zip_file_path)

        message = {
            "openlane_flow": "complted",
            "design_folder": request.design_folder,
            "blob_url": blob_url
        }
        logging.info("Successfully uploaded to Azure Blob. Now sending RabbitMQ message.")
        
        # Send message to RabbitMQ after successful upload
        publish_to_rabbitmq(message)

        return {"message": "Folder zipped and uploaded successfully", "blob_url": blob_url}
    
    except HTTPException as e:
        raise e
    except Exception as e:
        logging.error(f"Failed to upload folder: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to upload folder: {str(e)}")
        
