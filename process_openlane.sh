#!/bin/bash

# Check if OpenLane directory exists; if not, clone the repository
if [ ! -d "OpenLane" ]; then
    git clone --depth 1 https://github.com/The-OpenROAD-Project/OpenLane.git
fi
cd OpenLane || { echo "Failed to navigate to OpenLane directory"; exit 1; }

NEW_FOLDER="design_$(date +%Y%m%d_%H%M%S)"
mkdir designs/"$NEW_FOLDER"
chmod -R 777 designs/"$NEW_FOLDER"
chown -R 1000:1000 designs/"$NEW_FOLDER"
cp designs/spm/config.json designs/spm/pin_order.cfg designs/"$NEW_FOLDER"
mkdir designs/"$NEW_FOLDER"/src
cp designs/spm/src/spm.sdc designs/"$NEW_FOLDER"/src
# Check if a URL was provided
if [ -z "$1" ]; then
    echo "No Verilog URL provided."
    exit 1
fi

# Download the Verilog file
curl -o "designs/$NEW_FOLDER/src/spm.v" "$1"
make
make test
make mount
