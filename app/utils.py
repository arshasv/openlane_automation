import os
import requests
from .config import LOCAL_FILE_PATH

def download_blob(blob_url, download_path):
    """Download a blob from the provided URL."""
    try:
        # Ensure the directory for local files exists
        os.makedirs(LOCAL_FILE_PATH, exist_ok=True)
        
        # Send GET request to download the file
        response = requests.get(blob_url)
        response.raise_for_status()  # Raise an error for bad responses
        
        # Write the content to a local file
        with open(download_path, "wb") as download_file:
            download_file.write(response.content)
        print(f"Downloaded file from {blob_url} to {download_path}")
        
    except Exception as e:
        raise Exception(f"Failed to download blob: {str(e)}")
