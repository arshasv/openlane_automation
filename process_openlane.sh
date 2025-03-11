#!/bin/bash

# Ensure the openlane2 directory exists; if not, clone it
if [ ! -d "openlane2" ]; then
    git clone https://github.com/efabless/openlane2.git || { echo "Failed to clone OpenLane2 repository"; exit 1; }
fi

# Navigate to the openlane2 directory
cd openlane2 || { echo "Failed to navigate to OpenLane directory"; exit 1; }

# Fix ownership of the /app/openlane2 directory
chown -R $(whoami):$(whoami) /app/openlane2 || { echo "Failed to fix ownership of /app/openlane2"; exit 1; }

# Create the 'designs' directory if it doesn't exist
if [ ! -d "designs" ]; then
    mkdir designs || { echo "Failed to create 'designs' directory"; exit 1; }
fi

# Copy the spm directory into the designs directory
cp -r /app/spm designs || { echo "Failed to copy /app/spm to designs"; exit 1; }

# Create a new folder with a timestamp
NEW_FOLDER="design_$(date +%Y%m%d_%H%M%S)"
mkdir -p "designs/$NEW_FOLDER" || { echo "Failed to create new design folder"; exit 1; }

# Write the folder name to info.txt
echo "$NEW_FOLDER" > designs/info.txt || { echo "Failed to write to info.txt"; exit 1; }

# Set permissions for the new folder
chmod -R 777 "designs/$NEW_FOLDER" || { echo "Failed to set permissions for $NEW_FOLDER"; exit 1; }
chown -R $(whoami):$(whoami) "designs/$NEW_FOLDER" || { echo "Failed to set ownership for $NEW_FOLDER"; exit 1; }

# Create the 'src' subdirectory inside the new folder
mkdir -p "designs/$NEW_FOLDER/src" || { echo "Failed to create src directory"; exit 1; }

# Copy configuration files into the new folder
cp designs/spm/config.tcl designs/spm/pin_order.cfg "designs/$NEW_FOLDER" || { echo "Failed to copy configuration files"; exit 1; }

# Copy the SDC file into the 'src' subdirectory
cp designs/spm/src/spm.sdc "designs/$NEW_FOLDER/src" || { echo "Failed to copy SDC file"; exit 1; }

# Check if BLOB_URL is provided
if [ -z "$BLOB_URL" ]; then
    echo "Error: No Verilog URL provided."
    exit 1
fi

# Download the Verilog file from the provided URL
wget "$BLOB_URL" -O "designs/$NEW_FOLDER/src/spm.v" || { echo "Failed to download Verilog file"; exit 1; }

git config --global --add safe.directory /app/openlane2

nix-shell --command "openlane designs/$NEW_FOLDER/config.tcl" || { echo "OpenLane flow failed"; exit 1; }

# Completion message
echo "OpenLane flow completed successfully for design $NEW_FOLDER"