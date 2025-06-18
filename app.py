from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List
import uvicorn
from config import generate_openroad_files, download_design_file

app = FastAPI(
    title="OpenROAD Configuration Generator API",
    description="API for generating OpenROAD configuration files",
    version="1.0.0"
)

# Define the pin configuration model
class PinConfiguration(BaseModel):
    N: List[str] = Field(..., description="List of pins for the North direction")
    S: List[str] = Field(..., description="List of pins for the South direction")
    E: List[str] = Field(..., description="List of pins for the East direction")
    W: List[str] = Field(..., description="List of pins for the West direction")

# Define the main request model
class OpenLanePayload(BaseModel):
    blob_url: str = Field(..., description="URL of the file to be processed")
    design_name: str = Field(..., description="Name of the design")
    clock_port: str = Field(..., description="Clock port name")
    clock_period: int = Field(..., description="Clock period in nanoseconds")
    die_area: str = Field(..., description="Die area in format 'xmin ymin xmax ymax', e.g. '0 0 600 600'")
    pin_configuration: PinConfiguration = Field(..., description="Pin configuration for all directions")

# Define the response model
class OpenROADResponse(BaseModel):
    downloaded_file: str
    tcl_config_file: str
    sdc_file: str
    pin_order_file: str
    message: str

@app.post("/generate_config", response_model=OpenROADResponse)
async def generate_config(request: OpenLanePayload):
    """
    Generate OpenROAD configuration files based on provided parameters
    """
    try:
        # Extract pin configurations
        north_pins = ",".join(request.pin_configuration.N)
        south_pins = ",".join(request.pin_configuration.S)
        east_pins = ",".join(request.pin_configuration.E)
        west_pins = ",".join(request.pin_configuration.W)

        # First download the design file
        downloaded_file = download_design_file(
            blob_url=request.blob_url,
            design_name=request.design_name,
            output_base_dir="/app/openlane2/designs"
        )
        
        if not downloaded_file:
            raise HTTPException(status_code=500, detail="Failed to download design file")
        
        # Generate configuration files
        tcl_file, sdc_file, pin_order_file = generate_openroad_files(
            design_name=request.design_name,
            clock_period=request.clock_period,
            clock_port=request.clock_port,
            north_pins=north_pins,
            south_pins=south_pins,
            east_pins=east_pins,
            west_pins=west_pins,
            output_base_dir="/app/openlane2/designs",
            die_area=request.die_area
        )
        
        return OpenROADResponse(
            downloaded_file=downloaded_file,
            tcl_config_file=tcl_file,
            sdc_file=sdc_file,
            pin_order_file=pin_order_file,
            message="OpenROAD configuration files generated successfully"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating files: {str(e)}")

@app.get("/")
async def root():
    """
    Root endpoint with basic API information
    """
    return {
        "message": "OpenROAD Configuration Generator API",
        "usage": "POST to /generate_config endpoint with required parameters",
        "docs": "/docs for OpenAPI documentation"
    }

# To run the server directly from this file
if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=9000, reload=True)