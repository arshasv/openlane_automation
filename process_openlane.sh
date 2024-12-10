#!/bin/bash 


if [ ! -d "openlane2" ]; then
    git clone https://github.com/efabless/openlane2
fi
cd openlane2 || { echo "Failed to navigate to OpenLane directory"; exit 1; }

mkdir designs
cp -r /app/spm designs
NEW_FOLDER="design_$(date +%Y%m%d_%H%M%S)"
chmod -R 777 designs
chown -R 1000:1000 designs
mkdir designs/"$NEW_FOLDER"
echo "$NEW_FOLDER" > designs/info.txt
chmod -R 777 designs/"$NEW_FOLDER"
chown -R 1000:1000 designs/"$NEW_FOLDER"
cp designs/spm/config.json designs/spm/pin_order.cfg designs/"$NEW_FOLDER"
mkdir designs/"$NEW_FOLDER"/src
cp designs/spm/src/spm.sdc designs/"$NEW_FOLDER"/src

if [ -z "$VERILOG_URL" ]; then
    echo "Error: No Verilog URL provided."
    exit 1
fi

wget "$VERILOG_URL" -O designs/"$NEW_FOLDER"/src/spm.v || { echo "Failed to download Verilog file"; exit 1; }

# Enter Nix shell and run OpenLane flow
nix-shell --command "openlane designs/$NEW_FOLDER/config.json" || { echo "OpenLane flow failed"; exit 1; }


echo "OpenLane flow completed successfully for design $NEW_FOLDER"
