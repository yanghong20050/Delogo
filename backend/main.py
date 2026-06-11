import os
import sys
import uuid
import json
import asyncio
import cv2
import numpy as np
import base64
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, BackgroundTasks
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI(title="Delogo Backend API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

active_connections = []
job_cancel_flags: dict[str, bool] = {}

class JobRequest(BaseModel):
    job_id: str
    input_files: list[str]
    output_dir: str = ""
    bbox: dict = None
    bboxes: list[dict] = []

@app.websocket("/ws/progress/{job_id}")
async def websocket_endpoint(websocket: WebSocket, job_id: str):
    await websocket.accept()
    active_connections.append((job_id, websocket))
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        active_connections.remove((job_id, websocket))

async def broadcast_msg(msg: dict):
    for jid, ws in active_connections:
        if jid == msg.get("job_id"):
            try:
                await ws.send_json(msg)
            except:
                pass

@app.post("/api/v1/jobs")
async def create_job(req: JobRequest, background_tasks: BackgroundTasks):
    job_cancel_flags[req.job_id] = False
    background_tasks.add_task(process_job, req.job_id, req.input_files, req.output_dir, req.bbox, req.bboxes)
    return {"status": "accepted", "job_id": req.job_id}

@app.post("/api/v1/jobs/{job_id}/cancel")
async def cancel_job(job_id: str):
    job_cancel_flags[job_id] = True
    return {"status": "cancelled"}

async def process_job(job_id: str, files: list, output_dir: str, bbox: dict, bboxes: list):
    await asyncio.sleep(0.5)
    
    if not output_dir:
        output_dir = "/tmp/delogo_out"
    os.makedirs(output_dir, exist_ok=True)
        
    await broadcast_msg({"status": "starting_engine", "job_id": job_id})

    for i, file_path in enumerate(files):
        if job_cancel_flags.get(job_id, False):
            print(f"[DEBUG] Job {job_id} was cancelled before processing {file_path}")
            await broadcast_msg({
                "status": "cancelled",
                "job_id": job_id
            })
            break

        print(f"[DEBUG] Processing file {i+1}: {file_path}")
        await broadcast_msg({
            "status": "processing",
            "job_id": job_id,
            "progress": 50,
            "current_file": os.path.basename(file_path)
        })
        
        try:
            image = cv2.imread(file_path)
            if image is None:
                continue
            height, width = image.shape[:2]
            
            mask = np.zeros((height, width), dtype=np.uint8)
            
            # Fallback to single bbox if provided but no bboxes list
            if not bboxes and bbox:
                target_bboxes = [bbox]
            else:
                target_bboxes = bboxes
            
            for b in target_bboxes:
                x = int(b.get('x', 0) * width)
                y = int(b.get('y', 0) * height)
                b_w = int(b.get('w', 0) * width)
                b_h = int(b.get('h', 0) * height)
                cv2.rectangle(mask, (x, y), (x + b_w, y + b_h), 255, -1)
            
            mask_path = os.path.join("/tmp", f"mask_{job_id}_{i+1}.png")
            cv2.imwrite(mask_path, mask)
            
            import subprocess
            cmd = [
                sys.executable, "-m", "iopaint", "run",
                "--model=lama", "--device=mps",
                f"--image={file_path}",
                f"--mask={mask_path}",
                f"--output={output_dir}"
            ]
            print(f"[DEBUG] Running iopaint CLI: {' '.join(cmd)}")
            proc = await asyncio.create_subprocess_exec(*cmd)
            await proc.communicate()
            print(f"[DEBUG] iopaint CLI completed for {file_path}")
            
            base_name = os.path.splitext(os.path.basename(file_path))[0]
            res_path = os.path.join(output_dir, f"{base_name}.png")
            
            await broadcast_msg({
                "status": "file_done",
                "job_id": job_id,
                "file": file_path,
                "result_path": res_path
            })
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            await broadcast_msg({
                "status": "error",
                "job_id": job_id,
                "message": f"Error processing file {i+1}: {str(e)}"
            })
            continue

    await broadcast_msg({
        "status": "completed",
        "job_id": job_id,
        "progress": 100
    })

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
