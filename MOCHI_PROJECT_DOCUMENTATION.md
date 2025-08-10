# Mochi Text-to-Video API Project Documentation

## Overview
This document captures the complete journey of building a production-ready text-to-video API using the Mochi model, including architecture decisions, implementation details, debugging processes, and lessons learned.

## Project Goals
- **Primary**: Build a functional text-to-video API using the Mochi model
- **Architecture**: V1 setup with Redis for job queueing, FastAPI server, and GPU worker pods
- **Infrastructure**: Kubernetes deployment on H100 GPU cluster
- **Frontend**: Production web interface for video generation

## Architecture Overview

### V1 Architecture (Current Implementation)
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend UI   │    │   FastAPI API   │    │     Redis       │
│  (Jinja2 HTML) │◄──►│     Server      │◄──►│   Job Queue     │
│                 │    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │  Worker Pods    │
                       │ (2x H100 GPUs)  │
                       │  Mochi Model    │
                       └─────────────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │ Shared Storage  │
                       │  (NVMe Drive)   │
                       │ Models + Videos │
                       └─────────────────┘
```

### Component Details

#### 1. API Server (FastAPI + Jinja2)
- **Technology**: FastAPI with integrated Jinja2 frontend
- **Container**: `hshubhang/mochi-api:latest`
- **Ports**: 8000 (internal), 80 (service)
- **Key Features**:
  - Job submission and management
  - Video file serving
  - Integrated web UI
  - Health checks and monitoring

#### 2. Worker Pods
- **Technology**: Python + HuggingFace Diffusers
- **Container**: `hshubhang/mochi-worker:latest`
- **Resources**: 2x NVIDIA H100 80GB per pod, 2 pods total
- **GPU Strategy**: `device_map="balanced"` for memory distribution

#### 3. Storage Strategy
- **Location**: `/mnt/mochi-storage/` on GPU node (g451)
- **Model Weights**: `/mnt/mochi-storage/model-weights/`
- **Video Output**: `/mnt/mochi-storage/video-output/`
- **HuggingFace Cache**: `/mnt/mochi-storage/hf-cache/`

## Implementation Timeline

### Phase 1: Planning and Setup
**Decisions Made:**
- Kubernetes over Docker Compose for scalability
- Redis for job queue management
- FastAPI for REST API
- HuggingFace Diffusers for model inference
- NVMe storage for performance

**Alternative Approaches Considered:**
- Streamlit vs HTML/CSS/JS vs FastAPI+Jinja2
- NodePort vs LoadBalancer vs Ingress
- Separate frontend service vs integrated frontend

### Phase 2: Infrastructure Setup
**GPU Node Preparation:**
```bash
# Dependency installation scripts
./dependenciesone.sh  # CUDA drivers + container runtime
./dependenciestwo.sh  # Kubernetes components
```

**Storage Setup:**
```bash
# Created storage directories on NVMe drive
sudo mkdir -p /mnt/mochi-storage/{model-weights,video-output,hf-cache}
sudo chmod 755 /mnt/mochi-storage/
```

**Model Download:**
```bash
# Downloaded Mochi model weights (63GB)
huggingface-cli download genmo/mochi-1-preview \
  --local-dir /mnt/mochi-storage/model-weights/mochi-1-preview/
```

### Phase 3: API Development

#### FastAPI Server Implementation
**File Structure:**
```
api-server/
├── main.py              # FastAPI app with Jinja2 integration
├── requirements.txt     # Python dependencies
├── Dockerfile          # Container definition
└── templates/
    └── index.html      # Integrated frontend
```

**Key API Endpoints:**
- `POST /generate-video` - Submit video generation job
- `GET /jobs/{job_id}` - Get job status
- `GET /jobs` - List all jobs
- `GET /videos/{job_id}` - Download generated video
- `GET /health` - Health check
- `GET /` - Frontend interface

**Input Validation:**
```python
class VideoRequest(BaseModel):
    prompt: str
    duration: Optional[int] = Field(default=10, ge=1, le=30)
    fps: Optional[int] = Field(default=24, ge=1, le=24)
    resolution: Optional[str] = Field(default="480p")
    
    @field_validator('resolution')
    @classmethod
    def validate_resolution(cls, v):
        allowed = ["480p", "720p", "1080p"]
        if v not in allowed:
            raise ValueError(f"Resolution must be one of {allowed}")
        return v
```

### Phase 4: Worker Development

#### Multi-File Worker Architecture
**File Structure:**
```
worker/
├── worker.py           # Main worker process
├── model_loader.py     # Mochi model management
├── requirements.txt    # Worker dependencies
└── Dockerfile         # Container with CUDA support
```

**Model Loading Strategy:**
```python
# model_loader.py
self.pipeline = MochiPipeline.from_pretrained(
    self.model_path,
    torch_dtype=torch.bfloat16,
    device_map="balanced"  # Distributes across multiple GPUs
)
# Memory optimizations
self.pipeline.enable_vae_slicing()
self.pipeline.enable_vae_tiling()
```

**Job Processing Flow:**
1. Poll Redis queue with `BRPOP`
2. Load job parameters
3. Generate video with Mochi model
4. Save to shared storage
5. Update job status
6. Clear GPU memory

### Phase 5: Kubernetes Deployment

#### Service Architecture
**Redis (Job Queue):**
```yaml
# ClusterIP service for internal communication
spec:
  type: ClusterIP
  ports:
    - port: 6379
```

**API Server:**
```yaml
# LoadBalancer service for external access
spec:
  type: LoadBalancer
  ports:
    - port: 80
      targetPort: 8000
```

**Storage Volumes:**
```yaml
# hostPath volumes for shared storage
volumes:
  - name: model-weights-storage
    hostPath:
      path: /mnt/mochi-storage/model-weights
      type: Directory
  - name: video-storage
    hostPath:
      path: /mnt/mochi-storage/video-output
      type: DirectoryOrCreate
```

### Phase 6: Frontend Integration

#### Architecture Evolution
**Initial Plan**: Separate Nginx frontend service
**Final Implementation**: Integrated Jinja2 templates

**Benefits of Integration:**
- Eliminates CORS issues
- Simplifies deployment (single service)
- Reduces complexity
- Better performance (same origin)

**Frontend Features:**
- Video generation form
- Real-time job status polling
- Video preview and download
- Job history

## Major Debugging Sessions

### 1. NodePort vs LoadBalancer Issues
**Problem**: External access not working
**Root Cause**: Cluster lacks LoadBalancer implementation
**Solution**: Switched to NodePort services
**Learning**: Infrastructure constraints affect service design

### 2. Missing Templates Directory
**Problem**: `{"detail":"Not Found"}` on frontend access
**Root Cause**: Built container with wrong tag (`mochi-frontend` vs `mochi-api`)
**Debug Process**:
```bash
kubectl exec -it deployment/mochi-api -- ls -la /app/
# Result: No templates/ directory
```
**Solution**: Rebuild with correct tag
**Learning**: Container tag consistency is critical

### 3. CUDA Out of Memory (OOM)
**Problem**: Jobs failing with GPU memory errors
**Symptoms**:
```
CUDA out of memory. Tried to allocate 11.65 GiB 
(GPU 1; 80.00 GiB total capacity; 67.03 GiB already allocated)
```
**Analysis**: 
- Model requires ~60GB VRAM for single GPU
- Memory not released after failed attempts
- Higher FPS/duration increases memory requirements

**Solutions Implemented**:
```python
# Added memory cleanup
torch.cuda.empty_cache()
torch.cuda.ipc_collect()

# Added environment variable
PYTORCH_CUDA_ALLOC_CONF: "expandable_segments:True"
```

**Temporary Fixes**:
- Restart worker pods to clear memory
- Use conservative parameters (5s, 8fps, 480p)

### 4. GPU Utilization Inefficiency
**Observation**: Only 1 GPU at 100%, others at 0%
**Investigation**: Model architecture limitation
**Understanding**: 
- `device_map="balanced"` distributes model weights
- Inference computation still bottlenecks on single GPU
- This is model-level behavior, not setup error

## Performance Characteristics

### Current Capabilities
- **Model**: Mochi-1-preview (63GB)
- **GPU Memory**: ~30-32GB per GPU for model weights
- **Processing Time**: ~2-3 minutes for 5s video at 8fps
- **Stable Parameters**: duration ≤ 10s, fps ≤ 16, resolution 480p

### Limitations Identified
- **Memory**: 10s/24fps videos cause OOM
- **Compute**: Inference limited to single GPU
- **Throughput**: ~1 video per worker pod at a time

## Tools and Technologies Used

### Development Tools
- **Container Registry**: Docker Hub
- **Build Platform**: `--platform linux/amd64` for compatibility
- **Version Control**: Git with commit tracking

### Monitoring and Debugging
- **GPU Monitoring**: `nvidia-smi`
- **Container Inspection**: `kubectl exec -it`
- **Log Analysis**: `kubectl logs`
- **Network Testing**: `curl` with verbose output

### Infrastructure
- **Kubernetes**: v1.32.4
- **Container Runtime**: containerd
- **GPU**: 8x NVIDIA H100 80GB HBM3
- **Storage**: NVMe drives for high-speed access

## Configuration Management

### Environment Variables
**API Server:**
```yaml
env:
  - name: REDIS_HOST
    value: "redis"
  - name: REDIS_PORT
    value: "6379"
```

**Worker:**
```yaml
env:
  - name: REDIS_HOST
    value: "redis"
  - name: HF_HOME
    value: "/app/hf_cache"
  - name: MODEL_PATH
    value: "/app/model-weights/mochi-1-preview/"
  - name: PYTORCH_CUDA_ALLOC_CONF
    value: "expandable_segments:True"
```

### Resource Allocation
**Worker Pods:**
```yaml
resources:
  limits:
    nvidia.com/gpu: "2"
  requests:
    nvidia.com/gpu: "2"
```

## Security Considerations

### Secrets Management
- HuggingFace token stored as Kubernetes secret
- Model access through gated repository
- No sensitive data in container images

### Network Security
- Internal Redis communication only
- External access through defined LoadBalancer
- No direct pod exposure

## Future Optimizations (V2 Roadmap)

### Performance Improvements
1. **xDiT Integration**: True tensor parallelism
2. **Pipeline Optimization**: Gradient checkpointing
3. **Memory Management**: Dynamic allocation
4. **Caching**: Intelligent model component caching

### Scalability Enhancements
1. **Horizontal Pod Autoscaler**: Dynamic scaling
2. **Job Prioritization**: Queue management
3. **Resource Pooling**: GPU sharing strategies
4. **Circuit Breaker**: Failure handling

### Monitoring and Observability
1. **Metrics Collection**: Prometheus integration
2. **Performance Tracking**: Per-job timing
3. **Resource Monitoring**: GPU utilization trends
4. **Alert System**: Failure notifications

## Lessons Learned

### Technical Insights
1. **Container Tags Matter**: Inconsistent tagging causes silent failures
2. **GPU Memory is Finite**: Model size determines job parameters
3. **Model Architecture Limits**: Not all inefficiencies are fixable
4. **Volume Mounts**: Critical for shared state in distributed systems

### Architectural Decisions
1. **Integrated Frontend**: Simpler than microservices for this scale
2. **hostPath Storage**: Sufficient for single-node deployment
3. **Redis Queue**: Reliable for job management
4. **Rolling Updates**: Zero-downtime deployments work well

### Debugging Strategies
1. **Layer-by-Layer**: Verify each component independently
2. **Container Inspection**: Direct access reveals truth
3. **Parallel Investigation**: Use multiple terminals effectively
4. **Log Everything**: Comprehensive logging saves time

## Current Status

### Deployment State
- ✅ API Server: Running and accessible
- ✅ Worker Pods: 2 pods with 2 GPUs each
- ✅ Redis: Stable job queue
- ✅ Frontend: Integrated web interface
- ✅ Storage: Shared NVMe volumes

### Operational Capabilities
- ✅ Job submission via web UI
- ✅ Real-time status tracking
- ✅ Video generation and download
- ✅ Health monitoring
- ✅ Memory cleanup after jobs

### Known Issues
- ⚠️  GPU memory limitations for long/high-FPS videos
- ⚠️  Single-GPU inference bottleneck
- ⚠️  Manual worker restart needed after OOM

## Appendix

### Key Commands Reference
```bash
# Build and deploy API
cd api-server
docker build --platform linux/amd64 -t hshubhang/mochi-api:latest .
docker push hshubhang/mochi-api:latest
kubectl rollout restart deployment mochi-api

# Build and deploy Worker
cd worker
docker build --platform linux/amd64 -t hshubhang/mochi-worker:latest .
docker push hshubhang/mochi-worker:latest
kubectl rollout restart deployment mochi-worker

# Access services
kubectl port-forward svc/mochi-api-service 8080:80

# Debug containers
kubectl exec -it deployment/mochi-api -- bash
kubectl logs -l app=mochi-worker --tail=100

# Monitor GPU
ssh ubuntu@gpu-node
nvidia-smi
```

### File Locations
- **Project Root**: `/Users/shubhanghasabnis/voltage_park_mochi`
- **GPU Node Storage**: `/mnt/mochi-storage/`
- **Container Images**: Docker Hub `hshubhang/*`
- **Kubernetes Manifests**: `k8s/` directory

---

**Last Updated**: August 10, 2025  
**Version**: V1 Production Deployment  
**Status**: Operational with documented limitations
