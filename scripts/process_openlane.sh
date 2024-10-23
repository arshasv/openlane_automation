#!/bin/bash

# Install OpenLane and process the .v file
if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <path_to_v_file>"
    exit 1
fi

V_FILE=$1

# Clone OpenLane repository
git clone --depth 1 https://github.com/The-OpenROAD-Project/OpenLane.git
cd OpenLane/

# Copy the .v file to the OpenLane design directory
mkdir -p ./designs/spm/src
cp $V_FILE ./designs/spm/src/latest_generated_code.v

# Ensure permissions are set for the designs folder
chmod -R 777 ./designs/spm
chown -R 1000:1000 ./designs/spm

# Install OpenLane dependencies
make
make test
make mount

# Run the OpenLane flow for the design
./flow.tcl -design spm
