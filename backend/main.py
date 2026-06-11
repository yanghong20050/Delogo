import os
import sys
import uuid
import json
import asyncio
import cv2
import numpy as np
import base64
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
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
async def create_job(job_data: dict):
    asyncio.create_task(process_job(job_data))
    return {"status": "accepted", "job_id": job_data.get("job_id")}

async def process_job(job_data: dict):
    await asyncio.sleep(0.5)
    
    job_id = job_data.get("job_id")
    files = job_data.get("input_files", [])
    output_dir = job_data.get("output_dir", "")
    bbox = job_data.get("bbox")
    
    if not output_dir:
        output_dir = "/tmp/delogo_out"
    os.makedirs(output_dir, exist_ok=True)
        
    await broadcast_msg({"status": "starting_engine", "job_id": job_id})

    for i, file_path in enumerate(files):
        print(f"[DEBUG] Processing file {i+1}: {file_path}")
        await broadcast_msg({
            "status": "processing",
            "job_id": job_id,
            "progress": int((i / len(files)) * 100),
            "current_file": os.path.basename(file_path)
        })
        
        try:
            image = cv2.imread(file_path)
            if image is None:
                continue
            height, width = image.shape[:2]
            
            mask = np.zeros((height, width), dtype=np.uint8)
            
            if bbox:
                x = int(bbox.get('x', 0) * width)
                y = int(bbox.get('y', 0) * height)
                b_w = int(bbox.get('w', 0) * width)
                b_h = int(bbox.get('h', 0) * height)
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
            
            res_path = os.path.join(output_dir, os.path.basename(file_path))
            
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
