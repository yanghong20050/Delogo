import os
import sys
import multiprocessing

if __name__ == '__main__':
    multiprocessing.freeze_support()
    # If the executable is called with "iopaint_start", we route it to iopaint
    if len(sys.argv) > 1 and sys.argv[1] == "iopaint_start":
        # Remove 'iopaint_start' from sys.argv so iopaint parses the rest
        sys.argv.pop(1)
        from iopaint import entry_point
        sys.exit(entry_point())


import uuid
import json
import asyncio
import cv2
import numpy as np
import base64
import subprocess
import httpx
import time
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
iopaint_proc: subprocess.Popen = None
engine_ready: bool = False
last_activity_time = time.time()

async def idle_monitor():
    global iopaint_proc, engine_ready
    while True:
        await asyncio.sleep(10)
        if engine_ready and (time.time() - last_activity_time > 300):
            print("[DEBUG] Idle timeout (5 mins) reached. Killing iopaint sidecar to save memory.")
            if iopaint_proc:
                iopaint_proc.terminate()
                iopaint_proc.wait()
            iopaint_proc = None
            engine_ready = False

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(idle_monitor())

async def ensure_engine_running():
    global iopaint_proc, engine_ready
    if not engine_ready or iopaint_proc is None or iopaint_proc.poll() is not None:
        if sys.platform == "darwin":
            device_type = "mps"
        else:
            try:
                import torch
                if torch.cuda.is_available():
                    device_type = "cuda"
                else:
                    device_type = "cpu"
            except ImportError:
                device_type = "cpu"
        
        if getattr(sys, 'frozen', False):
            # Bundled mode: spawn ourselves with iopaint_start
            model_dir = os.path.join(sys._MEIPASS, "models")
            cmd = [
                sys.executable, "iopaint_start", "start",
                "--model=lama", f"--device={device_type}",
                "--port=8080", "--model-dir", model_dir
            ]
        else:
            # Dev mode: spawn via current python
            dev_model_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
            cmd = [
                sys.executable, "-m", "iopaint", "start",
                "--model=lama", f"--device={device_type}",
                "--port=8080", "--model-dir", dev_model_dir
            ]
            
        print(f"[DEBUG] Lazy loading: Starting iopaint sidecar: {' '.join(cmd)}")
        if getattr(sys, 'frozen', False):
            log_dir = os.path.expanduser('~/.delogo')
        else:
            log_dir = os.path.dirname(os.path.abspath(__file__))
            
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, 'delogo-engine.log')
        log_file = open(log_path, 'a')
        print(f'[DEBUG] Redirecting iopaint logs to {log_path}')
        iopaint_proc = subprocess.Popen(cmd, stdout=log_file, stderr=subprocess.STDOUT)
        
        # Poll the server until it's ready (max 60 seconds)
        for _ in range(60):
            try:
                async with httpx.AsyncClient() as client:
                    res = await client.get("http://127.0.0.1:8080/", timeout=1.0)
                    if res.status_code == 200:
                        engine_ready = True
                        print("[DEBUG] iopaint sidecar is ready!")
                        return
            except httpx.RequestError:
                pass
            await asyncio.sleep(1)
        
        print("[WARNING] iopaint sidecar did not respond in 60 seconds, but proceeding anyway.")

@app.on_event("shutdown")
async def shutdown_event():
    global iopaint_proc
    if iopaint_proc:
        print("[DEBUG] Terminating iopaint sidecar...")
        iopaint_proc.terminate()
        iopaint_proc.wait()

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
    global last_activity_time
    last_activity_time = time.time()
    
    if not output_dir:
        output_dir = "/tmp/delogo_out"
    os.makedirs(output_dir, exist_ok=True)
        
    await broadcast_msg({"status": "starting_engine", "job_id": job_id})
    
    # Lazy load the engine ONLY when the first job arrives
    await ensure_engine_running()

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
            
            # Encode image to Base64
            _, img_encoded = cv2.imencode('.jpg', image)
            img_b64 = base64.b64encode(img_encoded).decode('utf-8')
            
            # Encode mask to Base64
            _, mask_encoded = cv2.imencode('.png', mask)
            mask_b64 = base64.b64encode(mask_encoded).decode('utf-8')
            
            data_payload = {
                'image': f"data:image/jpeg;base64,{img_b64}",
                'mask': f"data:image/png;base64,{mask_b64}",
                'ldm_steps': 25,
                'ldm_sampler': 'plms',
                'hd_strategy': 'Crop',
                'hd_strategy_crop_margin': 128,
                'cv2_radius': 4,
            }
            
            print(f"[DEBUG] Sending HTTP request to iopaint sidecar for {file_path}")
            async with httpx.AsyncClient(trust_env=False) as client:
                res = await client.post(
                    "http://127.0.0.1:8080/api/v1/inpaint",
                    json=data_payload,
                    timeout=120.0
                )
                
                if res.status_code != 200:
                    raise Exception(f"iopaint server returned {res.status_code}: {res.text}")
                
                print(f"[DEBUG] iopaint sidecar returned success for {file_path}")
                # Decode bytes to image
                res_img_array = np.frombuffer(res.content, np.uint8)
                res_img = cv2.imdecode(res_img_array, cv2.IMREAD_COLOR)
                
                # Write to disk with exact original extension!
                res_path = os.path.join(output_dir, os.path.basename(file_path))
                cv2.imwrite(res_path, res_img)
            
            last_activity_time = time.time()
            
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
