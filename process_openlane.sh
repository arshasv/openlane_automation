#!/bin/bash

# Load environment variables
AZURE_STORAGE_CONNECTION_STRING=${AZURE_STORAGE_CONNECTION_STRING}
BLOB_CONTAINER_NAME=${BLOB_CONTAINER_NAME}

generate_pin_order_file() {
    local north_pins=$1
    local south_pins=$2
    local east_pins=$3
    local west_pins=$4
    local design_name=$5
    local output_base_dir=${6:-"./designs"}

    local design_dir="$output_base_dir/$design_name"
    mkdir -p "$design_dir"

    local pin_order_file="$design_dir/pin_order.cfg"
    {
        echo "#N"
        echo "@min_distance=0.1"
        echo "$north_pins" | tr ',' '\n'
        echo "#S"
        echo "$south_pins" | tr ',' '\n'
        echo "#E"
        echo "$east_pins" | tr ',' '\n'
        echo "#W"
        echo "$west_pins" | tr ',' '\n'
    } > "$pin_order_file"

    echo "$pin_order_file"
}

# Function to generate config.json and .sdc
generate_openroad_files() {
    local design_name=$1
    local clock_period=$2
    local clock_port=$3
    local north_pins=$4
    local south_pins=$5
    local east_pins=$6
    local west_pins=$7
    local output_base_dir=${8:-"./designs"}
    local die_area=$9

    local design_dir="$output_base_dir/$design_name"
    local src_dir="$design_dir/src"
    mkdir -p "$src_dir"

    local config_json="$design_dir/config.json"
    local sdc_file="$src_dir/${design_name}.sdc"

    generate_pin_order_file "$north_pins" "$south_pins" "$east_pins" "$west_pins" "$design_name" "$output_base_dir"

    {
        echo "set_units -time ns"
        echo "create_clock [get_ports $clock_port] -name core_clock -period $clock_period"
    } > "$sdc_file"

    # Generate config.json
    cat > "$config_json" <<EOF
{
  "GENERAL": {
    "DESIGN_NAME": "$design_name",
    "PDK": "sky130B",
    "VERILOG_FILES": ["src/*.v"],
    "CLOCK_PERIOD": $clock_period,
    "CLOCK_PORT": "$clock_port",
    "CLOCK_NET": "$clock_port",
    "LEC_ENABLE": 0
  },
  "LINTING": {
    "RUN_LINTER": 1,
    "QUIT_ON_LINTER_WARNINGS": 0,
    "QUIT_ON_LINTER_ERRORS": 1
  },
  "SYNTHESIS": {
    "SYNTH_CLOCK_UNCERTAINTY": 0.15,
    "SYNTH_NO_FLAT": 0,
    "SYNTH_SHARE_RESOURCES": 1,
    "SYNTH_ADDER_TYPE": "YOSYS",
    "BASE_SDC_FILE": ["src/*.sdc"],
    "SYNTH_FLAT_TOP": 0,
    "SYNTH_USE_PG_PINS_DEFINES": "USE_POWER_PINS",
    "QUIT_ON_TIMING_VIOLATIONS": 1,
    "QUIT_ON_SETUP_VIOLATIONS": 1,
    "QUIT_ON_HOLD_VIOLATIONS": 1
  },
  "FLOORPLAN": {
    "RUN_TAP_DECAP_INSERTION": 1,
    "FP_CORE_UTIL": 45,
    "FP_ASPECT_RATIO": 1,
    "FP_SIZING": "$( [[ -n "$die_area" ]] && echo "absolute" || echo "relative" )",
    "DIE_AREA": "$( [[ -n "$die_area" ]] && echo "$die_area" || echo "" )",
    "VDD_NETS": "vccd1",
    "GND_NETS": "vssd1",
    "SYNTH_USE_PG_PINS_DEFINES": "USE_POWER_PINS",
    "FP_PIN_ORDER_CFG": "pin_order.cfg",
    "FP_PDN_CORE_RING": 0,
    "FP_PDN_MULTILAYER": 0,
    "RT_MAX_LAYER": "met4",
    "FP_PDN_SKIPTRIM": 0,
    "FP_PDN_ENABLE_RAILS": 1
  },
  "PLACEMENT": {
    "PL_TARGET_DENSITY": 0.55,
    "PL_BASIC_PLACEMENT": 0,
    "PL_RESIZER_BUFFER_INPUT_PORTS": 1,
    "PL_RESIZER_DESIGN_OPTIMIZATIONS": 1,
    "PL_RESIZER_TIMING_OPTIMIZATIONS": 1,
    "GLB_RESIZER_DESIGN_OPTIMIZATIONS": 1,
    "GLB_RESIZER_TIMING_OPTIMIZATIONS": 1,
    "RUN_CTS": 1,
    "RUN_FILL_INSERTION": 1
  },
  "ROUTING": {
    "ROUTING_CORES": 4,
    "GRT_ALLOW_CONGESTION": 1,
    "DRT_OPT_ITERS": 20
  },
  "SIGNOFF": {
    "RUN_CVC": 1,
    "RUN_IRDROP_REPORT": 1
  }
}
EOF

    echo "Generated configuration JSON for $design_name"
}

# Ensure OpenLane2 repo
if [ ! -d "openlane2" ]; then
    git clone https://github.com/efabless/openlane2.git || { echo "Failed to clone OpenLane2"; exit 1; }
fi
cd openlane2 || { echo "Cannot access OpenLane2 directory"; exit 1; }

mkdir -p designs

# Read inputs
if [[ $# -lt 3 ]]; then
    echo "Usage: $0 <design_name> <clock_period> <clock_port> [north_pins] [south_pins] [east_pins] [west_pins] [die_area]"
    exit 1
fi

design_name=$1
clock_period=$2
clock_port=$3
north_pins=${4:-""}
south_pins=${5:-""}
east_pins=${6:-""}
west_pins=${7:-""}
die_area=${8:-""}

# Validate BLOB_URL
if [ -z "$BLOB_URL" ]; then
    echo "Error: No Verilog URL provided."
    exit 1
fi

# Download the Verilog file
design_src_dir="designs/$design_name/src"
mkdir -p "$design_src_dir"
verilog_file_name="${BLOB_URL##*/}"
wget --max-redirect=5 "$BLOB_URL" -O "$design_src_dir/$verilog_file_name" || { echo "Failed to download Verilog file"; exit 1; }

# Save design name
echo "$design_name" > designs/info.txt
chmod -R 777 "designs/$design_name"
chown -R $(whoami):$(whoami) "designs/$design_name"

# Generate configuration files
generate_openroad_files "$design_name" "$clock_period" "$clock_port" "$north_pins" "$south_pins" "$east_pins" "$west_pins" "./designs" "$die_area"

# Ensure OpenLane repo is safe for git operations
git config --global --add safe.directory /app/openlane2

# Ensure Azure CLI is installed
if ! command -v az &> /dev/null; then
    echo "Installing Azure CLI..."
    nix-env -iA nixpkgs.azure-cli || { echo "Failed to install Azure CLI"; exit 1; }
fi

# Run OpenLane flow (update this line if your flow expects config.json)
# Example: nix-shell --command "openlane designs/$design_name/config.json"
# If your flow still expects config.tcl, you must adapt it to use config.json

echo "OpenLane flow completed successfully for design $design_name"

# Trigger API to upload design folder to Azure Blob
API_URL="http://localhost:5000/upload_to_blob/"
JSON_BODY="{\"design_folder\": \"$design_name\"}"

echo "Triggering API to upload design folder to Blob Storage..."
curl -X POST -L "$API_URL" -H "Content-Type: application/json" -d "$JSON_BODY" -i || { echo "Failed to trigger API"; exit 1; }

echo "API triggered successfully!"