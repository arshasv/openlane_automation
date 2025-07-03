# import subprocess
# import os
# import zipfile
# import logging
# import json
# import asyncio
# import aio_pika
# from fastapi import FastAPI, HTTPException
# from pydantic import BaseModel
# from azure.storage.blob import BlobServiceClient
# from dotenv import load_dotenv
# from typing import List

# # Load environment variables from .env file
# load_dotenv()

# # Configure logging
# logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# # FastAPI app instance
# app = FastAPI()

# # Pydantic models
# class PinConfiguration(BaseModel):
#     N: List[str]
#     S: List[str]
#     E: List[str]
#     W: List[str]

# class VerilogRequest(BaseModel):
#     blob_url: str
#     design_name: str
#     clock_port: str
#     clock_period: float
#     pin_configuration: PinConfiguration

# class UploadRequest(BaseModel):
#     design_folder: str

# # Constants
# SCRIPT_PATH = "./process_openlane.py"
# AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
# BLOB_CONTAINER_NAME = os.getenv("BLOB_CONTAINER_NAME")
# RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
# RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", 5672))
# RABBITMQ_QUEUE = os.getenv("RABBITMQ_QUEUE", "verilog_queue")
# RABBITMQ_USER = os.getenv("RABBITMQ_USER", "guest")
# RABBITMQ_PASSWORD = os.getenv("RABBITMQ_PASSWORD", "guest")

# # Async RabbitMQ publisher
# async def publish_to_rabbitmq_async(message: dict):
#     try:
#         logging.info(f"[aio_pika] Publishing message to RabbitMQ: {message}")
#         connection = await aio_pika.connect_robust(
#             f"amqp://{RABBITMQ_USER}:{RABBITMQ_PASSWORD}@{RABBITMQ_HOST}:{RABBITMQ_PORT}/"
#         )
#         async with connection:
#             channel = await connection.channel()
#             await channel.declare_queue(RABBITMQ_QUEUE, durable=True)

#             await channel.default_exchange.publish(
#                 aio_pika.Message(
#                     body=json.dumps(message).encode(),
#                     delivery_mode=aio_pika.DeliveryMode.PERSISTENT
#                 ),
#                 routing_key=RABBITMQ_QUEUE,
#             )
#             logging.info("[aio_pika] Message sent successfully.")
#     except Exception as e:
#         logging.error(f"[aio_pika] Failed to send message to RabbitMQ: {str(e)}")

# # Sync-safe wrapper for FastAPI
# def publish_to_rabbitmq(message: dict):
#     try:
#         asyncio.run(publish_to_rabbitmq_async(message))
#     except RuntimeError as e:
#         # Handles already-running event loop in async servers like uvicorn
#         logging.warning(f"RuntimeError: {str(e)} — using existing loop")
#         loop = asyncio.get_event_loop()
#         loop.create_task(publish_to_rabbitmq_async(message))

# # Function to run log_monitor.py in the background
# def run_log_monitor():
#     try:
#         command = ["python3", "/app/log_monitor.py"]
#         logging.info(f"Starting log_monitor.py in background: {' '.join(command)}")
#         subprocess.Popen(
#             command,
#             stdout=subprocess.DEVNULL,
#             stderr=subprocess.DEVNULL,
#             start_new_session=True
#         )
#         logging.info("log_monitor.py launched successfully in background.")
#     except Exception as e:
#         logging.error(f"Failed to start log_monitor.py: {str(e)}")

# # Function to execute the OpenLane shell script
# def run_shell_script(request: VerilogRequest):
#     try:
#         os.environ['BLOB_URL'] = request.blob_url
#         os.environ['DESIGN_NAME'] = request.design_name
#         os.environ['CLOCK_PORT'] = request.clock_port
#         os.environ['CLOCK_PERIOD'] = str(request.clock_period)
#         os.environ['PINS_N'] = ','.join(request.pin_configuration.N)
#         os.environ['PINS_S'] = ','.join(request.pin_configuration.S)
#         os.environ['PINS_E'] = ','.join(request.pin_configuration.E)
#         os.environ['PINS_W'] = ','.join(request.pin_configuration.W)

#         command = [
#             "python3", SCRIPT_PATH,
#             request.design_name,
#             str(request.clock_period),
#             request.clock_port,
#             ','.join(request.pin_configuration.N),
#             ','.join(request.pin_configuration.S),
#             ','.join(request.pin_configuration.E),
#             ','.join(request.pin_configuration.W),
#         ]
#         logging.info(f"Executing OpenLane script: {' '.join(command)}")

#         result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
#         logging.info(f"Shell script stdout: {result.stdout}")
#         logging.error(f"Shell script stderr: {result.stderr}")

#         if result.returncode != 0:
#             raise Exception(f"Shell script failed: {result.stderr}")

#         logging.info("OpenLane shell script completed successfully.")
#         return {"status": "success", "message": "OpenLane flow completed successfully"}
#     except Exception as e:
#         logging.error(f"OpenLane execution failed: {str(e)}")
#         raise HTTPException(status_code=500, detail=f"OpenLane execution failed: {str(e)}")

# # Function to zip a folder
# def zip_folder(folder_path: str):
#     try:
#         zip_filename = f"{folder_path}.zip"
#         with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
#             for root, _, files in os.walk(folder_path):
#                 for file in files:
#                     file_path = os.path.join(root, file)
#                     arcname = os.path.relpath(file_path, folder_path)
#                     zipf.write(file_path, arcname)
#         return zip_filename
#     except Exception as e:
#         logging.error(f"Failed to zip folder: {str(e)}")
#         raise HTTPException(status_code=500, detail=f"Failed to zip folder: {str(e)}")

# # Function to upload a file to Azure Blob Storage
# def upload_to_azure_blob(file_path: str):
#     try:
#         blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
#         blob_client = blob_service_client.get_blob_client(container=BLOB_CONTAINER_NAME, blob=os.path.basename(file_path))
#         with open(file_path, "rb") as data:
#             blob_client.upload_blob(data, overwrite=True)
#         blob_url = f"https://{blob_client.account_name}.blob.core.windows.net/{BLOB_CONTAINER_NAME}/{os.path.basename(file_path)}"
#         logging.info(f"File uploaded to Azure Blob Storage: {blob_url}")
#         return blob_url
#     except Exception as e:
#         logging.error(f"Failed to upload file to Azure Blob Storage: {str(e)}")
#         raise HTTPException(status_code=500, detail=f"Failed to upload file to Azure Blob Storage: {str(e)}")

# # Endpoint: Run OpenLane + start log monitor
# @app.post("/run_openlane")
# def run_openlane(request: VerilogRequest):
#     run_log_monitor()
#     return run_shell_script(request)

# # Endpoint: Zip folder, upload to Blob, notify via RabbitMQ
# @app.post("/upload_to_blob")
# async def upload_to_blob(request: UploadRequest):
#     try:
#         design_folder_path = f"openlane2/designs/{request.design_folder}"
#         if not os.path.exists(design_folder_path):
#             logging.error(f"Design folder not found: {design_folder_path}")
#             raise HTTPException(status_code=404, detail=f"Design folder not found: {design_folder_path}")

#         zip_file_path = zip_folder(design_folder_path)
#         blob_url = upload_to_azure_blob(zip_file_path)
#         os.remove(zip_file_path)

#         message = {
#             "openlane_flow": "completed",
#             "design_folder": request.design_folder,
#             "blob_url": blob_url
#         }

#         logging.info(f"Sending completion message to RabbitMQ: {message}")
#         publish_to_rabbitmq(message)

#         return {"message": "Folder zipped and uploaded successfully", "blob_url": blob_url}

#     except HTTPException as e:
#         raise e
#     except Exception as e:
#         logging.error(f"Failed to upload folder: {str(e)}")
#         raise HTTPException(status_code=500, detail=f"Failed to upload folder: {str(e)}")







import subprocess
import os
import zipfile
import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv
from typing import List

# ✅ Use async publisher directly
from rabbitmq_utils import publish_message_async

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

app = FastAPI()

# Models
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
    pin_configuration: PinConfiguration

class UploadRequest(BaseModel):
    design_folder: str

SCRIPT_PATH = "./process_openlane.py"
AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
BLOB_CONTAINER_NAME = os.getenv("BLOB_CONTAINER_NAME")

def run_log_monitor():
    try:
        command = ["python3", "/app/log_monitor.py"]
        logging.info(f"Launching log_monitor: {' '.join(command)}")
        subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )
        logging.info("log_monitor.py started in background.")
    except Exception as e:
        logging.error(f"Failed to start log_monitor.py: {str(e)}")

def run_shell_script(request: VerilogRequest):
    try:
        os.environ['BLOB_URL'] = request.blob_url
        os.environ['DESIGN_NAME'] = request.design_name
        os.environ['CLOCK_PORT'] = request.clock_port
        os.environ['CLOCK_PERIOD'] = str(request.clock_period)
        os.environ['PINS_N'] = ','.join(request.pin_configuration.N)
        os.environ['PINS_S'] = ','.join(request.pin_configuration.S)
        os.environ['PINS_E'] = ','.join(request.pin_configuration.E)
        os.environ['PINS_W'] = ','.join(request.pin_configuration.W)

        command = [
            "python3", SCRIPT_PATH,
            request.design_name,
            str(request.clock_period),
            request.clock_port,
            ','.join(request.pin_configuration.N),
            ','.join(request.pin_configuration.S),
            ','.join(request.pin_configuration.E),
            ','.join(request.pin_configuration.W),
        ]

        logging.info(f"Executing OpenLane script: {' '.join(command)}")
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        logging.info(f"OpenLane stdout: {result.stdout}")
        if result.stderr:
            logging.warning(f"OpenLane stderr: {result.stderr}")

        if result.returncode != 0:
            raise Exception(f"Shell script failed with error: {result.stderr}")

        logging.info("OpenLane flow completed successfully.")
        return {"status": "success", "message": "OpenLane flow completed successfully"}

    except Exception as e:
        logging.error(f"OpenLane flow failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"OpenLane execution failed: {str(e)}")

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
        raise HTTPException(status_code=500, detail=f"Zipping failed: {str(e)}")

def upload_to_azure_blob(file_path: str):
    try:
        blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
        blob_client = blob_service_client.get_blob_client(container=BLOB_CONTAINER_NAME, blob=os.path.basename(file_path))
        with open(file_path, "rb") as data:
            blob_client.upload_blob(data, overwrite=True)
        blob_url = f"https://{blob_client.account_name}.blob.core.windows.net/{BLOB_CONTAINER_NAME}/{os.path.basename(file_path)}"
        logging.info(f"File uploaded to Azure Blob: {blob_url}")
        return blob_url
    except Exception as e:
        logging.error(f"Azure upload failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Blob upload failed: {str(e)}")

@app.post("/run_openlane")
def run_openlane(request: VerilogRequest):
    run_log_monitor()
    return run_shell_script(request)

@app.post("/upload_to_blob")
async def upload_to_blob(request: UploadRequest):
    try:
        design_folder_path = f"openlane2/designs/{request.design_folder}"
        if not os.path.exists(design_folder_path):
            raise HTTPException(status_code=404, detail=f"Design folder not found: {design_folder_path}")

        zip_file_path = zip_folder(design_folder_path)
        blob_url = upload_to_azure_blob(zip_file_path)
        os.remove(zip_file_path)

        message = {
            "openlane_flow": "completed",
            "design_folder": request.design_folder,
            "blob_url": blob_url
        }

        logging.info(f"📤 Sending message to RabbitMQ from main.py: {message}")
        await publish_message_async(message)

        return {"message": "Folder zipped and uploaded successfully", "blob_url": blob_url}

    except HTTPException as e:
        raise e
    except Exception as e:
        logging.error(f"Upload and publish failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")
