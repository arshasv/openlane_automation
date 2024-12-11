import subprocess
import os
import zipfile
import uuid
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv
import shutil

# Load environment variables from .env file
load_dotenv()


# FastAPI app instance
app = FastAPI()

# Pydantic model for input validation
class VerilogRequest(BaseModel):
    verilog_url: str

class UploadRequest(BaseModel):
    design_folder: str

# Constants for shell script and Azure Blob Storage
SCRIPT_PATH = "./process_openlane.sh"

# Azure Blob Storage details
AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
BLOB_CONTAINER_NAME = os.getenv("BLOB_CONTAINER_NAME")

# Function to execute the shell script
def run_shell_script(verilog_url: str):
    try:
        os.environ['VERILOG_URL'] = verilog_url
        
        result = subprocess.run(
            ["bash", SCRIPT_PATH],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        if result.returncode != 0:
            raise Exception(f"Shell script failed: {result.stderr}")

        return result.stdout
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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
        raise HTTPException(status_code=500, detail=f"Failed to zip folder: {str(e)}")

# Function to upload a file to Azure Blob Storage
def upload_to_azure_blob(file_path: str):
    try:
        blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
        blob_client = blob_service_client.get_blob_client(container=BLOB_CONTAINER_NAME, blob=os.path.basename(file_path))
        
        with open(file_path, "rb") as data:
            blob_client.upload_blob(data, overwrite=True)

        return f"File uploaded to Azure Blob Storage: {blob_client.url}"
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload file to Azure Blob Storage: {str(e)}")

# API endpoint to trigger OpenLane process
@app.post("/run_openlane")
async def run_openlane(request: VerilogRequest):
    try:
        output = run_shell_script(request.verilog_url)
        return {"message": "OpenLane flow completed successfully", "output": output}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to run OpenLane: {str(e)}")

# API endpoint to zip and upload a folder to Azure Blob Storage
@app.post("/upload_to_blob")
async def upload_to_blob(request: UploadRequest):
    try:
        design_folder_path = f"openlane2/designs/{request.design_folder}"
        if not os.path.exists(design_folder_path):
            raise HTTPException(status_code=404, detail=f"Design folder not found: {design_folder_path}")
        
        zip_file_path = zip_folder(design_folder_path)
        blob_url = upload_to_azure_blob(zip_file_path)

        # Clean up zip file after upload
        os.remove(zip_file_path)

        return {"message": "Folder zipped and uploaded successfully", "blob_url": blob_url}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload folder: {str(e)}")
