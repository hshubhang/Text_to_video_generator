import os
import uuid
from datetime import datetime
from typing import Optional

import redis
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastapi.responses import FileResponse 

from fastapi.templating import Jinja2Templates
from fastapi import Request, Form
from fastapi.responses import RedirectResponse

templates = Jinja2Templates(directory="templates")




app = FastAPI(title="Mochi 1 text to video generation API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class VideoRequest(BaseModel):
    prompt: str
    duration: Optional[int] = 10
    fps: Optional[int] = 8
    resolution: Optional[str] = "480p"

class JobStatus(BaseModel):
    job_id: str
    status: str
    error_message: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    video_url: Optional[str] = None

redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "redis"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    decode_responses=True
)

def create_job(request: VideoRequest) -> str:
    job_id = str(uuid.uuid4())
    job_data = {
        "job_id": job_id,
        "status": "pending",
        "prompt": request.prompt,
        "duration": request.duration,
        "fps": request.fps,
        "resolution": request.resolution,
        "created_at": str(datetime.utcnow()),
        "updated_at": str(datetime.utcnow()),
    }
    redis_client.hset(f"job:{job_id}", mapping=job_data)
    redis_client.lpush("job_queue", job_id)
    return job_id

def get_job_status(job_id: str) -> dict:
    job_data = redis_client.hgetall(f"job:{job_id}")
    if not job_data:
        raise HTTPException(status_code=404, detail="Job not found")
    return job_data

@app.post("/generate-video", response_model = dict)
async def generate_video(request: VideoRequest):
    try:
        job_id = create_job(request)
        return {"job_id": job_id, "status": "pending"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/jobs/{job_id}", response_model=JobStatus)
async def get_status(job_id: str):
    try:
        job_data = get_job_status(job_id)

        if job_data["status"] == "completed":
            job_data["video_url"] = f"/videos/{job_id}"
        return JobStatus(**job_data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/jobs")
async def job_list():
    try:
        # Simple v1: just get all job IDs from the queue
        job_ids = redis_client.lrange("job_queue", 0, -1)
        jobs = []
        for job_id in job_ids:
            job_data = redis_client.hgetall(f"job:{job_id}")
            if job_data:
                jobs.append(job_data)
        return {"jobs": jobs, "total": len(jobs)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    try:
        redis_client.ping()
        return {"status": "healthy", "redis_status": "connected"}
    except:
        return {"status": "unhealthy", "redis_status": "disconnected"}

@app.get("/videos/{job_id}")
async def get_video(job_id: str):
    try:
        job_data = get_job_status(job_id)
        if job_data.get("status") != "completed":
            raise HTTPException(status_code=400, detail="Video is not ready yet or video not found")

        
        video_filename = f"{job_id}.mp4"
        
        video_path = f"/app/videos/{video_filename}"

        if not os.path.exists(video_path):
            raise HTTPException(status_code=404, detail="Video file not found")

        return FileResponse(
            path = video_path,
            media_type="video/mp4",
            filename=video_filename
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


#Jinja2 code

@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/submit-video")
async def submit_video(
    request: Request,
    prompt: str = Form(...),
    duration: int = Form(10),
    fps: int = Form(8)
):
    try:
        # Use your existing create_job function
        video_request = VideoRequest(prompt=prompt, duration=duration, fps=fps)
        job_id = create_job(video_request)
        return RedirectResponse(url=f"/job/{job_id}", status_code=303)
    except Exception as e:
        return templates.TemplateResponse("index.html", {
            "request": request, 
            "error": str(e)
        })

@app.get("/job/{job_id}")
async def job_status_page(request: Request, job_id: str):
    try:
        job_data = get_job_status(job_id)
        return templates.TemplateResponse("index.html", {
            "request": request,
            "job": job_data
        })
    except Exception:
        return templates.TemplateResponse("index.html", {
            "request": request,
            "error": "Job not found"
        })

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)




