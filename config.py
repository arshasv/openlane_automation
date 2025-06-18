#!/usr/bin/env python3

import os
import sys
import requests
import json
from urllib.parse import urlparse
import argparse
import shutil

def download_design_file(blob_url, design_name, output_base_dir="/app/openlane2/designs"):
    """
    Download a design file from a URL and save it to a folder named after the design.
    
    Args:
        blob_url (str): URL of the file to download
        design_name (str): Name of the design, used for the folder name
        output_base_dir (str): Base directory for outputs
    
    Returns:
        str: Path to the downloaded file
    """
    # Create design directory structure
    design_dir = os.path.join(output_base_dir, design_name)
    src_dir = os.path.join(design_dir, "src")
    
    # Ensure directories exist
    os.makedirs(design_dir, exist_ok=True)
    os.makedirs(src_dir, exist_ok=True)
    
    # Get the filename from the URL
    parsed_url = urlparse(blob_url)
    filename = os.path.basename(parsed_url.path)
    
    # If filename is empty or not provided in URL, use a default name
    if not filename:
        filename = f"{design_name}"
    
    # Full path for the downloaded file
    file_path = os.path.join(src_dir, filename)
    
    try:
        # Download the file
        response = requests.get(blob_url, stream=True)
        response.raise_for_status()  # Raise an exception for HTTP errors
        
        # Save the file
        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        print(f"Successfully downloaded design file: {file_path}")
        return file_path
    
    except requests.exceptions.RequestException as e:
        print(f"Error downloading file: {e}")
        return None

def generate_pin_order_file(north_pins, south_pins, east_pins, west_pins, design_name, output_base_dir="."):
    """
    Generate a pin_order.cfg file with pin directions in the design folder.
    
    Args:
        north_pins (str): Comma-separated list of pins for North direction
        south_pins (str): Comma-separated list of pins for South direction
        east_pins (str): Comma-separated list of pins for East direction
        west_pins (str): Comma-separated list of pins for West direction
        design_name (str): Name of the design, used for the folder name
        output_base_dir (str): Base directory for outputs
    
    Returns:
        str: Path to the generated pin_order.cfg file
    """
    # Create design directory
    design_dir = os.path.join(output_base_dir, design_name)
    os.makedirs(design_dir, exist_ok=True)
    
    # Define the output file path
    pin_order_file = os.path.join(design_dir, "pin_order.cfg")
    
    # Process the pin lists (split by commas and remove whitespace)
    north_pin_list = [pin.strip() for pin in north_pins.split(",") if pin.strip()]
    south_pin_list = [pin.strip() for pin in south_pins.split(",") if pin.strip()]
    east_pin_list = [pin.strip() for pin in east_pins.split(",") if pin.strip()]
    west_pin_list = [pin.strip() for pin in west_pins.split(",") if pin.strip()]
    
    # Generate pin order content
    pin_order_content = "#N\n@min_distance=0.1\n"
    for pin in north_pin_list:
        pin_order_content += f"{pin}\n"
    
    pin_order_content += "#S\n"
    for pin in south_pin_list:
        pin_order_content += f"{pin}\n"
    
    pin_order_content += "#E\n"
    for pin in east_pin_list:
        pin_order_content += f"{pin}\n"
    
    pin_order_content += "#W\n"
    for pin in west_pin_list:
        pin_order_content += f"{pin}\n"
    
    # Write to the pin_order.cfg file
    with open(pin_order_file, 'w') as f:
        f.write(pin_order_content)
    
    print(f"Pin order file generated: {pin_order_file}")
    return pin_order_file

def generate_openroad_files(design_name, clock_period, clock_port, 
                          north_pins, south_pins, east_pins, west_pins,
                          output_base_dir=".", die_area=None):
    """
    Generate TCL config, SDC, and pin_order files in a single function.
    
    Args:
        design_name (str): The name of the design
        clock_period (int/float): Clock period in nanoseconds
        clock_port (str): Clock port name
        north_pins (str): Comma-separated list of pins for North direction
        south_pins (str): Comma-separated list of pins for South direction
        east_pins (str): Comma-separated list of pins for East direction
        west_pins (str): Comma-separated list of pins for West direction
        output_base_dir (str): Base directory for outputs
        die_area (str, optional): Die area in format "xmin ymin xmax ymax", e.g. "0 0 600 600"
    
    Returns:
        tuple: Paths to the generated (tcl_file, sdc_file, pin_order_file)
    """
    # Create design directory structure
    design_dir = os.path.join(output_base_dir, design_name)
    src_dir = os.path.join(design_dir, "src")
    
    # Ensure directories exist
    os.makedirs(design_dir, exist_ok=True)
    os.makedirs(src_dir, exist_ok=True)
    
    # Define file paths
    config_file = os.path.join(design_dir, f"{design_name}_config.tcl")
    sdc_file = os.path.join(src_dir, f"{design_name}.sdc")
    
    # Generate pin order file
    pin_order_file = generate_pin_order_file(north_pins, south_pins, east_pins, west_pins, design_name, output_base_dir)
    
    # Generate SDC content
    sdc_content = f"""set_units -time ns
create_clock [get_ports {clock_port}]  -name core_clock  -period {clock_period}"""
    
    # Write to the SDC file
    with open(sdc_file, 'w') as f:
        f.write(sdc_content)
    
    # Generate the floorplan sizing configuration based on die_area
    if die_area and die_area.strip():
        fp_sizing_section = f"""set ::env(FP_SIZING) "absolute"
set ::env(DIE_AREA) "{die_area}"
# set ::env(FP_SIZING) "relative" """
    else:
        fp_sizing_section = """set ::env(FP_SIZING) "relative"
# set ::env(FP_SIZING) "absolute"
# set ::env(DIE_AREA) "0 0 600 600" """
    
    # Generate TCL config content
    tcl_content = f"""##################################################################
# GENERAL
##################################################################
set ::env(DESIGN_NAME) "{design_name}"
set ::env(PDK) "sky130B"
set ::env(VERILOG_FILES) [glob $::env(DESIGN_DIR)/src/*.v]
set ::env(CLOCK_PERIOD) {clock_period}
set ::env(CLOCK_PORT) "{clock_port}"
set ::env(CLOCK_NET) "{clock_port}"
#set ::env(DESIGN_IS_CORE) 0
set ::env(LEC_ENABLE) 0
##################################################################
# LINTING
##################################################################
set ::env(RUN_LINTER) 1
set ::env(QUIT_ON_LINTER_WARNINGS) 0
set ::env(QUIT_ON_LINTER_ERRORS) 1
##################################################################
# SYNSTHESIS
##################################################################
set ::env(SYNTH_CLOCK_UNCERTAINTY) 0.25
set ::env(SYNTH_CLOCK_UNCERTAINTY) 0.15
# DELAY/AREA 0-4/0-3
#set ::env(SYNTH_STRATEGY) "DELAY 3"
set ::env(SYNTH_NO_FLAT) 0
set ::env(SYNTH_SHARE_RESOURCES) 1
# YOSYS/FA/RCA/CSA carry select adder
set ::env(SYNTH_ADDER_TYPE) "YOSYS"
set ::env(BASE_SDC_FILE) [glob $::env(DESIGN_DIR)/src/*.sdc]
set ::env(SYNTH_FLAT_TOP) 0
set ::env(SYNTH_USE_PG_PINS_DEFINES) "USE_POWER_PINS"
set ::env(QUIT_ON_TIMING_VIOLATIONS) 1
set ::env(QUIT_ON_SETUP_VIOLATIONS) 1
set ::env(QUIT_ON_HOLD_VIOLATIONS) 1
##################################################################
# FLOORPLAN
##################################################################
set ::env(RUN_TAP_DECAP_INSERTION) 1
set ::env(FP_CORE_UTIL) 45
set ::env(FP_ASPECT_RATIO) 1
{fp_sizing_section}
set ::env(VDD_NETS) "vccd1"
set ::env(GND_NETS) "vssd1"
set ::env(SYNTH_USE_PG_PINS_DEFINES) "USE_POWER_PINS"
set ::env(FP_PIN_ORDER_CFG) [glob $::env(DESIGN_DIR)/pin_order.cfg]
set ::env(FP_PDN_CORE_RING) 0
set ::env(FP_PDN_MULTILAYER) 0
set ::env(RT_MAX_LAYER) "met4"
set ::env(FP_PDN_SKIPTRIM) 0
set ::env(FP_PDN_ENABLE_RAILS) 1
#set ::env(FP_PDN_CORE_RING_VWIDTH) 3.1
#set ::env(FP_PDN_CORE_RING_HWIDTH) 3.1
#set ::env(FP_PDN_CORE_RING_VOFFSET) 12.45
#set ::env(FP_PDN_CORE_RING_HOFFSET) 12.45
#set ::env(FP_PDN_CORE_RING_VSPACING) 1.7
#set ::env(FP_PDN_CORE_RING_HSPACING) 1.7
#set ::env(FP_PDN_VWIDTH) 3.1
#set ::env(FP_PDN_HWIDTH) 3.1
#set ::env(FP_PDN_VSPACING) [expr::(5 * $FP_PDN_CORE_RING_VWIDTH)]
#set ::env(FP_PDN_HSPACING) [expr::(5 * $FP_PDN_CORE_RING_HWIDTH)]
#set ::env(FP_PDN_VPITCH) 180
#set ::env(FP_PDN_HPITCH) 180
#set ::env(FP_PDN_VOFFSET) 5
#set ::env(FP_PDN_HOFFSET) 5
##################################################################
# PLACEMENT
##################################################################
set ::env(PL_TARGET_DENSITY) 0.55 
set ::env(PL_BASIC_PLACEMENT) 0
set ::env(PL_RESIZER_BUFFER_INPUT_PORTS) 1
set ::env(PL_RESIZER_DESIGN_OPTIMIZATIONS) 1
set ::env(PL_RESIZER_TIMING_OPTIMIZATIONS) 1
set ::env(GLB_RESIZER_DESIGN_OPTIMIZATIONS) 1
set ::env(GLB_RESIZER_TIMING_OPTIMIZATIONS) 1
set ::env(RUN_CTS) 1 
set ::env(RUN_FILL_INSERTION) 1 
##################################################################
# ROUTING
##################################################################
set ::env(ROUTING_CORES) 4  
set ::env(GRT_ALLOW_CONGESTION) 1  
set ::env(DRT_OPT_ITERS) 20  
##################################################################
# SIGNOFF
##################################################################
set ::env(RUN_CVC) 1   
set ::env(RUN_IRDROP_REPORT) 1
"""
    
    # Write to the TCL config file
    with open(config_file, 'w') as f:
        f.write(tcl_content)
    
    print(f"Successfully generated files:")
    print(f"  TCL config file: {config_file}")
    print(f"  SDC file: {sdc_file}")
    print(f"  Pin order file: {pin_order_file}")
    
    if die_area and die_area.strip():
        print(f"  Floor plan sizing mode: ABSOLUTE")
        print(f"  Die area: {die_area}")
    else:
        print(f"  Floor plan sizing mode: RELATIVE")
    
    return config_file, sdc_file, pin_order_file

def process_api_response(api_data, output_base_dir="."):
    """
    Process API response data, download design files, and generate configuration files.
    
    Args:
        api_data (dict): API response data containing parameters and file URL
        output_base_dir (str): Base directory for outputs
    
    Returns:
        tuple: Paths to the downloaded file and generated config files
    """
    # Extract parameters from API response
    try:
        design_name = api_data.get('design_name')
        clock_period = float(api_data.get('clock_period', 10))
        clock_port = api_data.get('clock_port')
        north_pins = api_data.get('north_pins', '')
        south_pins = api_data.get('south_pins', '')
        east_pins = api_data.get('east_pins', '')
        west_pins = api_data.get('west_pins', '')
        blob_url = api_data.get('blob_url')
        die_area = api_data.get('die_area', '')
        
        # Validate required parameters
        if not design_name:
            raise ValueError("Missing required parameter: design_name")
        if not clock_port:
            raise ValueError("Missing required parameter: clock_port")
        if not blob_url:
            raise ValueError("Missing required parameter: blob_url")
        
        # Download the design file to the design-specific folder
        downloaded_file = download_design_file(blob_url, design_name, output_base_dir)
        if not downloaded_file:
            raise ValueError("Failed to download design file")
        
        # Generate configuration files
        config_file, sdc_file, pin_order_file = generate_openroad_files(
            design_name, clock_period, clock_port,
            north_pins, south_pins, east_pins, west_pins,
            output_base_dir, die_area
        )
        
        return downloaded_file, config_file, sdc_file, pin_order_file
    
    except (ValueError, KeyError) as e:
        print(f"Error processing API data: {e}")
        return None, None, None, None

def main():
    """
    Main function to handle command line arguments and generate the configuration files.
    """
    parser = argparse.ArgumentParser(description='OpenROAD Configuration Generator with API support')
    
    # Add API mode arguments
    parser.add_argument('--api', action='store_true', help='Run in API mode')
    parser.add_argument('--api-file', type=str, help='JSON file containing API response data')
    parser.add_argument('--api-json', type=str, help='Direct JSON string containing API response data')
    parser.add_argument('--output-dir', type=str, default=".", help='Base output directory')
    
    # Add original script arguments
    parser.add_argument('--design-name', type=str, help='Design name')
    parser.add_argument('--clock-period', type=float, help='Clock period in ns')
    parser.add_argument('--clock-port', type=str, help='Clock port name')
    parser.add_argument('--north-pins', type=str, help='North pins (comma-separated)')
    parser.add_argument('--south-pins', type=str, help='South pins (comma-separated)')
    parser.add_argument('--east-pins', type=str, help='East pins (comma-separated)')
    parser.add_argument('--west-pins', type=str, help='West pins (comma-separated)')
    parser.add_argument('--die-area', type=str, help='Die area (format: xmin ymin xmax ymax)')
    parser.add_argument('--file-url', type=str, help='URL to download design file from')
    
    args = parser.parse_args()
    
    # API Mode
    if args.api:
        api_data = None
        
        # Load API data from file
        if args.api_file:
            try:
                with open(args.api_file, 'r') as f:
                    api_data = json.load(f)
            except (json.JSONDecodeError, FileNotFoundError) as e:
                print(f"Error loading API file: {e}")
                sys.exit(1)
        
        # Or load API data from direct JSON string
        elif args.api_json:
            try:
                api_data = json.loads(args.api_json)
            except json.JSONDecodeError as e:
                print(f"Error parsing JSON string: {e}")
                sys.exit(1)
        
        # Process API data if available
        if api_data:
            downloaded_file, config_file, sdc_file, pin_order_file = process_api_response(
                api_data, args.output_dir
            )
            
            if downloaded_file:
                print("\nAPI mode completed successfully!")
                print(f"Files are ready for use with OpenROAD.")
            else:
                print("\nAPI mode failed.")
                sys.exit(1)
        else:
            print("No API data provided. Use --api-file or --api-json")
            sys.exit(1)
    
    # Command Line Arguments Mode
    elif args.design_name and args.clock_port:
        # Create design folder structure
        design_dir = os.path.join(args.output_dir, args.design_name)
        src_dir = os.path.join(design_dir, "src")
        os.makedirs(design_dir, exist_ok=True)
        os.makedirs(src_dir, exist_ok=True)
        
        # Check if we're downloading a file
        if args.blob_url:
            downloaded_file = download_design_file(args.blob_url, args.design_name, args.output_dir)
            if not downloaded_file:
                print("Failed to download design file.")
                sys.exit(1)
        
        # Generate configuration files
        generate_openroad_files(
            args.design_name,
            args.clock_period or 10.0,
            args.clock_port,
            args.north_pins or '',
            args.south_pins or '',
            args.east_pins or '',
            args.west_pins or '',
            args.output_dir,
            args.die_area
        )
        
        print("\nCommand line mode completed successfully!")
        print("Files are ready for use with OpenROAD.")
    
    # Interactive Mode
    elif len(sys.argv) <= 1 or (len(sys.argv) == 2 and (sys.argv[1] == '-h' or sys.argv[1] == '--help')):
        print("\nOpenROAD Configuration Generator")
        print("================================\n")
        
        print("Required parameters:")
        design_name = input("Enter design name: ")
        clock_period = float(input("Enter clock period (ns): "))
        clock_port = input("Enter clock port name: ")
        
        # Create design directory structure
        output_base_dir = input("Enter base output directory [default: current directory]: ")
        if output_base_dir.strip() == "":
            output_base_dir = "."
        
        design_dir = os.path.join(output_base_dir, design_name)
        src_dir = os.path.join(design_dir, "src")
        os.makedirs(design_dir, exist_ok=True)
        os.makedirs(src_dir, exist_ok=True)
        
        # Ask if the user wants to download a design file
        download_option = input("Do you want to download a design file? (y/n): ").strip().lower()
        
        if download_option == 'y':
            blob_url = input("Enter URL for the design file: ")
            downloaded_file = download_design_file(blob_url, design_name, output_base_dir)
            
            if not downloaded_file:
                print("Failed to download file. Continuing with configuration generation...")
        
        print("\nPin order configuration:")
        print("(Enter pins for each direction, separate multiple pins with commas)")
        north_pins = input("North pins: ")
        south_pins = input("South pins: ")
        east_pins = input("East pins: ")
        west_pins = input("West pins: ")
        
        print("\nOptional parameters (press Enter to use defaults):")
        die_area = input("Die area (format: 'xmin ymin xmax ymax', e.g. '0 0 600 600') [default: none - use relative sizing]: ")
        
        # Generate all files in a single flow
        generate_openroad_files(design_name, clock_period, clock_port, 
                              north_pins, south_pins, east_pins, west_pins,
                              output_base_dir, die_area)
        
        print(f"\nDone! Files are ready for use with OpenROAD in {design_dir}")
    
    else:
        parser.print_help()

if __name__ == "__main__":
    main()



