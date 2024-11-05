from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import subprocess

app = FastAPI()

class VerilogRequest(BaseModel):
    verilog_url: str

@app.post("/run_openlane/")
async def run_openlane(request: VerilogRequest):
    try:
        result = subprocess.run(
            ["./process_openlane.sh", request.verilog_url],
            check=True,
            text=True,
            capture_output=True
        )
        return {"status": "success", "output": result.stdout}
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail={"status": "error", "output": e.stderr})
