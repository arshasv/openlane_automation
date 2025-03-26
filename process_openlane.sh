#!/bin/bash

# Load environment variables
AZURE_STORAGE_CONNECTION_STRING=${AZURE_STORAGE_CONNECTION_STRING}
BLOB_CONTAINER_NAME=${BLOB_CONTAINER_NAME}

# Ensure the openlane2 directory exists; if not, clone it
if [ ! -d "openlane2" ]; then
    git clone https://github.com/efabless/openlane2.git || { echo "Failed to clone OpenLane2 repository"; exit 1; }
fi

# Navigate to the openlane2 directory
cd openlane2 || { echo "Failed to navigate to OpenLane directory"; exit 1; }

# Ensure necessary permissions for OpenLane directory
if [ ! -w "/app/openlane2" ]; then
    echo "Warning: Insufficient permissions for /app/openlane2. Skipping ownership change."
else
    chown -R $(whoami):$(whoami) /app/openlane2 || { echo "Failed to fix ownership of /app/openlane2"; exit 1; }
fi

# Create the 'designs' directory if it doesn't exist
mkdir -p designs || { echo "Failed to create 'designs' directory"; exit 1; }

# Copy the spm directory into the designs directory if it doesn't exist
if [ ! -d "designs/spm" ]; then
    cp -r /app/spm designs || { echo "Failed to copy /app/spm to designs"; exit 1; }
fi

# Create a new folder with a timestamp
NEW_FOLDER="design_$(date +%Y%m%d_%H%M%S)"
mkdir -p "designs/$NEW_FOLDER/src" || { echo "Failed to create new design folder"; exit 1; }

# Write the folder name to info.txt
echo "$NEW_FOLDER" > designs/info.txt || { echo "Failed to write to info.txt"; exit 1; }

# Set permissions for the new folder
chmod -R 777 "designs/$NEW_FOLDER"
chown -R $(whoami):$(whoami) "designs/$NEW_FOLDER" || { echo "Failed to set ownership for $NEW_FOLDER"; exit 1; }

# Copy configuration files into the new folder
cp designs/spm/config.tcl designs/spm/pin_order.cfg "designs/$NEW_FOLDER" || { echo "Failed to copy configuration files"; exit 1; }
cp designs/spm/src/spm.sdc "designs/$NEW_FOLDER/src" || { echo "Failed to copy SDC file"; exit 1; }

# Validate BLOB_URL
if [ -z "$BLOB_URL" ]; then
    echo "Error: No Verilog URL provided."
    exit 1
fi

# Download the Verilog file with redirect handling
wget --max-redirect=5 "$BLOB_URL" -O "designs/$NEW_FOLDER/src/spm.v" || { echo "Failed to download Verilog file"; exit 1; }

# Ensure OpenLane repo is safe for git operations
git config --global --add safe.directory /app/openlane2

# Ensure Azure CLI is installed
if ! command -v az &> /dev/null; then
    echo "Installing Azure CLI..."
    nix-env -iA nixpkgs.azure-cli || { echo "Failed to install Azure CLI"; exit 1; }
fi

# Run OpenLane flow
nix-shell --command "openlane designs/$NEW_FOLDER/config.tcl" || { echo "OpenLane flow failed"; exit 1; }

echo "OpenLane flow completed successfully for design $NEW_FOLDER"

# Trigger API to upload design folder to Azure Blob
API_URL="http://localhost:5000/upload_to_blob/"
JSON_BODY="{\"design_folder\": \"$NEW_FOLDER\"}"

echo "Triggering API to upload design folder to Blob Storage..."
curl -X POST -L "$API_URL" -H "Content-Type: application/json" -d "$JSON_BODY" -i || { echo "Failed to trigger API"; exit 1; }

echo "API triggered successfully!"
