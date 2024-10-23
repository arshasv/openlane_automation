import os
from dotenv import load_dotenv

load_dotenv()

# Azure Blob Configuration
AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
BLOB_CONTAINER_NAME = os.getenv("BLOB_CONTAINER_NAME")

# Local directory to store .v files
LOCAL_FILE_PATH = os.path.join(os.getcwd(), "local_files/")
