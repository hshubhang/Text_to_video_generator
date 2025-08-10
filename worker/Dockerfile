FROM nvidia/cuda:12.1.1-devel-ubuntu22.04

# Install Python and system dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-dev \
    ffmpeg \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt
RUN pip3 install --no-cache-dir --index-url https://download.pytorch.org/whl/cu121 torch

# Copy worker code
COPY worker.py .
COPY model_loader.py .

# Create directories for mounted volumes
RUN mkdir -p /app/model-weights /app/output /app/hf_cache

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV HF_HOME=/app/hf_cache

# Run worker
CMD ["python3", "worker.py"]
