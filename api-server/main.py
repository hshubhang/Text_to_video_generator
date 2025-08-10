import os
import uuid
from datetime import datetime
from typing import Optional

import redis
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

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

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)