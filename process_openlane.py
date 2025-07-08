import os
import sys
import subprocess
import json
import requests
from pathlib import Path

def generate_pin_order_file(north_pins, south_pins, east_pins, west_pins, design_name, output_base_dir="./designs"):
    design_dir = Path(output_base_dir) / design_name
    design_dir.mkdir(parents=True, exist_ok=True)
    pin_order_file = design_dir / "pin_order.cfg"
    with open(pin_order_file, "w") as f:
        f.write("#N\n")
        f.write("@min_distance=0.1\n")
        f.write('\n'.join(north_pins.split(',')) + '\n')
        f.write("#S\n")
        f.write('\n'.join(south_pins.split(',')) + '\n')
        f.write("#E\n")
        f.write('\n'.join(east_pins.split(',')) + '\n')
        f.write("#W\n")
        f.write('\n'.join(west_pins.split(',')) + '\n')
    return str(pin_order_file)

def generate_openroad_files(design_name, clock_period, clock_port, north_pins, south_pins, east_pins, west_pins, output_base_dir="./designs", die_area=""):
    design_dir = Path(output_base_dir) / design_name
    src_dir = design_dir / "src"
    src_dir.mkdir(parents=True, exist_ok=True)
    config_json = design_dir / "config.json"
    sdc_file = src_dir / f"{design_name}.sdc"

    generate_pin_order_file(north_pins, south_pins, east_pins, west_pins, design_name, output_base_dir)

    # Generate SDC file content based on clock period
    with open(sdc_file, "w") as f:
        if float(clock_period) == 0:
            # SDC constraints for combinational design (no clock)
            f.write("# SDC constraints for combinational design (no clock)\n")
            f.write("set_input_delay 0.1 [get_ports in*]\n")
            f.write("set_output_delay 0.1 [get_ports out*]\n")
        else:
            # SDC constraints for sequential design (with clock)
            f.write("set_units -time ns\n")
            f.write(f"create_clock [get_ports {clock_port}] -name core_clock -period {clock_period}\n")

    # Generate configuration JSON
    config = {
        "//": "Basics",
        "DESIGN_NAME": design_name,
        "VERILOG_FILES": "dir::src/*.v",
        "CLOCK_PERIOD": float(clock_period),
        "CLOCK_PORT": clock_port,
        "PNR_SDC_FILE": f"dir::src/{design_name}.sdc",
        "SIGNOFF_SDC_FILE": f"dir::src/{design_name}.sdc",
        "//": "PDN",
        "FP_PDN_VOFFSET": 5,
        "FP_PDN_HOFFSET": 5,
        "FP_PDN_VWIDTH": 2,
        "FP_PDN_HWIDTH": 2,
        "FP_PDN_VPITCH": 30,
        "FP_PDN_HPITCH": 30,
        "FP_PDN_SKIPTRIM": True,
        "//": "Pin Order",
        "FP_PIN_ORDER_CFG": "dir::pin_order.cfg",
        "//": "Technology-Specific Configs",
        "pdk::sky130*": {
            "FP_CORE_UTIL": 45,
            "CLOCK_PERIOD": float(clock_period),
            "scl::sky130_fd_sc_hs": {
                "CLOCK_PERIOD": 8
            },
            "scl::sky130_fd_sc_ls": {
                "MAX_FANOUT_CONSTRAINT": 5
            }
        },
        "pdk::gf180mcu*": {
            "CLOCK_PERIOD": 24.0,
            "FP_CORE_UTIL": 40,
            "MAX_FANOUT_CONSTRAINT": 4,
            "PL_TARGET_DENSITY": 0.5
        }
    }
    with open(config_json, "w") as f:
        json.dump(config, f, indent=4)
    print(f"Generated configuration JSON for {design_name}")

def trigger_api_to_upload_blob(design_name, status):
    """Trigger API to upload design folder to Azure Blob Storage."""
    api_url = "http://localhost:5000/upload_to_blob/"
    json_body = {"design_folder": design_name, "status": status}

    print(f"Triggering API to upload design folder to Blob Storage with status '{status}'...")
    response = requests.post(api_url, json=json_body, allow_redirects=True)
    if response.status_code == 200:
        print("API triggered successfully!")
    else:
        print(f"Failed to trigger API: {response.status_code}")
        sys.exit(1)

def main():
    # Check arguments
    if len(sys.argv) < 4:
        print("Usage: process_openlane.py <design_name> <clock_period> <clock_port> [north_pins] [south_pins] [east_pins] [west_pins] [die_area]")
        sys.exit(1)

    design_name = sys.argv[1]
    clock_period = sys.argv[2]
    clock_port = sys.argv[3]
    north_pins = sys.argv[4] if len(sys.argv) > 4 else ""
    south_pins = sys.argv[5] if len(sys.argv) > 5 else ""
    east_pins = sys.argv[6] if len(sys.argv) > 6 else ""
    west_pins = sys.argv[7] if len(sys.argv) > 7 else ""
    die_area = sys.argv[8] if len(sys.argv) > 8 else ""

    BLOB_URL = os.environ.get("BLOB_URL")
    if not BLOB_URL:
        print("BLOB_URL environment variable not set")
        sys.exit(1)

    # Ensure openlane2 repo
    if not Path("openlane2").is_dir():
        subprocess.run(["git", "clone", "https://github.com/efabless/openlane2.git"], check=True)
    os.chdir("openlane2")

    Path("designs").mkdir(exist_ok=True)

    # Download the Verilog file
    design_src_dir = Path("designs") / design_name / "src"
    design_src_dir.mkdir(parents=True, exist_ok=True)
    verilog_file_name = BLOB_URL.split("/")[-1]
    verilog_file_path = design_src_dir / verilog_file_name

    # Download using requests
    print(f"Downloading Verilog file from {BLOB_URL} ...")
    r = requests.get(BLOB_URL, allow_redirects=True)
    if r.status_code == 200:
        with open(verilog_file_path, "wb") as f:
            f.write(r.content)
    else:
        print("Failed to download Verilog file")
        sys.exit(1)

    # Save design name
    with open("designs/info.txt", "w") as f:
        f.write(design_name + "\n")

    # Set permissions (optional, may require root privileges)
    subprocess.run(["chmod", "-R", "777", f"designs/{design_name}"])
    subprocess.run(["chown", "-R", f"{os.getenv('USER', 'root')}:{os.getenv('USER', 'root')}", f"designs/{design_name}"])

    # Generate configuration files
    generate_openroad_files(design_name, clock_period, clock_port, north_pins, south_pins, east_pins, west_pins, "./designs", die_area)

    # Ensure OpenLane repo is safe for git operations
    subprocess.run(["git", "config", "--global", "--add", "safe.directory", os.getcwd()])

    # Ensure Azure CLI is installed
    if subprocess.run(["which", "az"], capture_output=True).returncode != 0:
        print("Installing Azure CLI...")
        subprocess.run(["nix-env", "-iA", "nixpkgs.azure-cli"], check=True)

    # Start log_monitor.py in the background
    log_monitor_proc = subprocess.Popen(["python3", "/app/log_monitor.py"])

    try:
        # Run OpenLane flow
        subprocess.run(["nix-shell", "--command", f"openlane designs/{design_name}/config.json"], check=True)
        print(f"OpenLane flow completed successfully for design {design_name}")
        status = "success"
    except subprocess.CalledProcessError as e:
        print(f"OpenLane flow failed with error: {e}")
        status = "failure"
    finally:
        # Ensure log_monitor is terminated
        log_monitor_proc.terminate()

        # Trigger API to upload design folder to Azure Blob Storage
        trigger_api_to_upload_blob(design_name, status)

if __name__ == "__main__":
    main()