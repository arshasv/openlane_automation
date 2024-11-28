import subprocess
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os

# FastAPI app instance
app = FastAPI()

# Pydantic model for input validation
class VerilogRequest(BaseModel):
    verilog_url: str

# Define the path to your shell script
SCRIPT_PATH = "./process_openlane.sh"

# Function to execute the shell script
def run_shell_script(verilog_url: str):
    try:
        # Set the Verilog URL environment variable
        os.environ['VERILOG_URL'] = verilog_url
        
        # Execute the shell script
        result = subprocess.run(
            ["bash", SCRIPT_PATH],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        if result.returncode != 0:
            raise Exception(f"Shell script failed: {result.stderr}")

        return result.stdout

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# API endpoint to trigger OpenLane process
@app.post("/run_openlane")
async def run_openlane(request: VerilogRequest):
    try:
        # Trigger the shell script with the provided Verilog URL
        output = run_shell_script(request.verilog_url)
        return {"message": "OpenLane flow completed successfully", "output": output}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to run OpenLane: {str(e)}")
