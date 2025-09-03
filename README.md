# Mochi Video Generation System

A distributed text-to-video generation system powered by the Mochi 1 model, built with FastAPI, Redis, and Kubernetes for scalable deployment.

## Overview

This system generates videos from text prompts using the Mochi 1 text-to-video model. It features a microservices architecture with a web interface, REST API, and scalable worker processing using Redis as a job queue.

## Architecture

The system consists of three main components:

- **API Server**: FastAPI web server that handles requests and serves the web interface
- **Worker**: GPU-powered processing nodes that generate videos using the Mochi model
- **Redis**: Message queue and job status storage

## Features

- Text-to-video generation using Mochi 1 model
- Web interface for easy video creation
- REST API for programmatic access
- Configurable video parameters (duration, FPS, resolution)
- Real-time job status tracking
- GPU memory management and error recovery
- Kubernetes deployment with health checks

## Project Structure

```
voltage_park_mochi/
├── api-server/
│   ├── main.py              # FastAPI application
│   ├── requirements.txt     # Python dependencies
│   ├── Dockerfile          # Container build instructions
│   └── templates/
│       └── index.html      # Web interface
├── worker/
│   ├── worker.py           # Main worker process
│   ├── model_loader.py     # Mochi model management
│   ├── requirements.txt    # ML dependencies
│   └── Dockerfile         # GPU-enabled container
└── k8s/
    ├── api-server.yaml    # API server deployment
    ├── worker.yaml        # Worker deployment
    └── redis.yaml         # Redis deployment
```

## Quick Start

### Prerequisites

- Kubernetes cluster with GPU nodes
- NVIDIA GPU with CUDA 12.1+ support
- Mochi 1 model weights (place in `/mnt/mochi-storage/model-weights/mochi-1-preview/`)

### Deployment

1. **Deploy Redis:**
   ```bash
   kubectl apply -f k8s/redis.yaml
   ```

2. **Deploy API Server:**
   ```bash
   kubectl apply -f k8s/api-server.yaml
   ```

3. **Deploy Workers:**
   ```bash
   kubectl apply -f k8s/worker.yaml
   ```

4. **Access the system:**
   - Web Interface: `http://<load-balancer-ip>`
   - API Documentation: `http://<load-balancer-ip>/docs`

## API Endpoints

### Generate Video
```http
POST /generate-video
Content-Type: application/json

{
  "prompt": "A cat playing in a garden",
  "duration": 10,
  "fps": 8,
  "resolution": "480p"
}
```

### Check Job Status
```http
GET /jobs/{job_id}
```

### Download Video
```http
GET /videos/{job_id}
```

### Health Check
```http
GET /health
```

## Configuration

### Video Parameters

- **Duration**: 5-10 seconds
- **FPS**: 8-24 (capped at 24 for safety)
- **Resolution**: 480p (480x848), 720p (720x1280), 1080p (1080x1920)
- **Inference Steps**: 64 (fixed for quality)

### Environment Variables

**API Server:**
- `REDIS_HOST`: Redis hostname (default: "redis")
- `REDIS_PORT`: Redis port (default: 6379)

**Worker:**
- `REDIS_HOST`: Redis hostname (default: "redis")
- `REDIS_PORT`: Redis port (default: 6379)
- `HF_HOME`: HuggingFace cache directory
- `OUTPUT_DIR`: Video output directory

## How It Works

1. **Job Creation**: User submits a video generation request via web interface or API
2. **Queue Management**: Job is added to Redis queue with unique ID
3. **Processing**: Available worker picks up job and loads Mochi model
4. **Generation**: Worker generates video frames using the text prompt
5. **Export**: Frames are exported to MP4 format
6. **Completion**: Job status is updated and video is available for download

## Technical Details

### GPU Requirements
- 2x NVIDIA GPUs per worker
- CUDA 12.1+ support
- Sufficient VRAM for Mochi model (varies by resolution)

### Model Loading
- Uses `torch.bfloat16` for memory efficiency
- Balanced device mapping across GPUs
- VAE tiling enabled for large resolutions

### Error Handling
- Automatic GPU memory cleanup on failures
- Job status tracking with error messages
- Redis connection retry logic

### Health Monitoring
- Readiness probes for service availability
- Liveness probes for automatic recovery
- GPU memory monitoring and logging

## Storage Requirements

The system uses persistent storage for:
- Model weights: `/mnt/mochi-storage/model-weights/`
- Video output: `/mnt/mochi-storage/video-output/`
- HuggingFace cache: `/mnt/mochi-storage/hf-cache/`

## Troubleshooting

### Common Issues

1. **Model not found**: Ensure Mochi weights are in correct path
2. **GPU memory errors**: Check GPU availability and memory usage
3. **Redis connection failed**: Verify Redis pod is running
4. **Worker not starting**: Check model weights and GPU resources

### Debug Commands

```bash
# Check pod status
kubectl get pods

# View worker logs
kubectl logs -f deployment/mochi-worker

# Check GPU usage
kubectl exec -it <worker-pod> -- nvidia-smi

# Test Redis connection
kubectl exec -it <api-pod> -- python -c "import redis; r=redis.Redis(); r.ping()"
```

## Development

### Local Setup

1. **Start Redis:**
   ```bash
   docker run -d -p 6379:6379 redis:7
   ```

2. **Install dependencies:**
   ```bash
   # API server
   cd api-server && pip install -r requirements.txt
   
   # Worker
   cd worker && pip install -r requirements.txt
   ```

3. **Run services:**
   ```bash
   # Terminal 1: API server
   cd api-server && python main.py
   
   # Terminal 2: Worker
   cd worker && python worker.py
   ```

### Building Images

```bash
# API server
cd api-server
docker build -t hshubhang/mochi-api:latest .

# Worker
cd worker
docker build -t hshubhang/mochi-worker:latest .
```

## Notes

- The system is configured for a specific GPU node (`g451`) in the worker deployment
- Workers are set to 4 replicas for high throughput
- Video files are served directly from the API server
- The web interface includes auto-refresh for job status updates

## License

This project is for educational and research purposes. Please ensure you have proper licensing for the Mochi 1 model before deployment.
