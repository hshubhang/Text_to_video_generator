import os
import time
import redis
import logging
import torch
import gc
from datetime import datetime
from diffusers.utils import export_to_video
from model_loader import MochiModelLoader


#logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class JobProcessor:
    def __init__(self):
        
        self.redis_client = redis.Redis(
            host=os.getenv("REDIS_HOST", "redis"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            decode_responses=True
        )

        self.model_loader = MochiModelLoader()
    
    def update_job_status(self, job_id: str, status: str, **kwargs):
        try:
            updates = {
                "status": status,
                "updated_at": str(datetime.utcnow()),
            }
            for key, value in kwargs.items():
                if value is not None:
                    updates[key] = str(value)

            self.redis_client.hset(f"job:{job_id}", mapping=updates)
            logger.info(f"Updated job {job_id} status to: {status}")
        except Exception as e:
            logger.error(f"Failed to update job {job_id} status: {e}")

    def process_job(self, job_id: str):

        start_time = time.time()
        try:
            job_data = self.redis_client.hgetall(f"job:{job_id}")
            if not job_data:
                logger.warning(f"Job {job_id} not found")
                return

            logger.info(f"Processing job {job_id}")

            #Extract job data
            prompt = job_data.get("prompt")
            duration = int(job_data.get("duration", 10))
            fps = int(job_data.get("fps", 8))
            resolution = job_data.get("resolution", "480p")
            
            # Cap FPS for safety
            if fps > 24:
                logger.warning(f"FPS {fps} too high, capping at 24 for V1")
                fps = 24
            
            #Update status to processing
            self.update_job_status(job_id, "processing")

            #generate video using Mochi pipeline
            logger.info(f"Generating video for prompt: {prompt} ({duration}s, {fps}fps, {resolution})")
            frames = self.model_loader.generate_video(
                prompt=prompt,
                duration=duration,
                resolution=resolution,
                fps=fps
            )

            output_dir = "/app/output"
            os.makedirs(output_dir, exist_ok=True)

            videofile_name = f"{job_id}.mp4"
            videofile_path = os.path.join(output_dir, videofile_name)

            duration = time.time() - start_time
            logger.info(f"Video generation completed in {duration:.2f} seconds")
            logger.info(f"Saving video to {videofile_path}")
            try:
                export_to_video(frames, videofile_path, fps=fps)
                logger.info(f"Video saved successfully: {videofile_path}")
            except Exception as e:
                logger.error(f"Failed to export video: {e}")
                raise

            self.update_job_status(
                job_id, 
                "completed",
                result=videofile_name,
                video_path=videofile_path
            )

            #Video generation is async, so we need to wait for it to complete
            logger.info(f"Video generation completed for job {job_id}")

        except Exception as e:
            logger.error(f"Failed to process job {job_id}: {e}")

            try:

                logger.info("Cleaning GPU memory after job failure.")
                torch.cuda.empty_cache()
                torch.cuda.ipc_collect()
                gc.collect()

                for i in range(torch.cuda.device_count()):
                    allocated_memory = torch.cuda.memory_allocated(i) / 1024 ** 3
                    logger.info(f"GPU {i} memory after cleanup: {allocated_memory:.1f} GB")

            except Exception as cleanup_error:
                logger.error(f"Memory cleanup failed: {cleanup_error}")

            self.update_job_status(job_id, "failed", error_message=str(e))

        
    def worker_loop(self):
        """Main worker loop - polls Redis for jobs"""
        logger.info("Worker started, polling for jobs...")
        
        while True:
            try:
                # Pop job from queue (blocking with 5 second timeout)
                result = self.redis_client.brpop("job_queue", timeout=5)
                
                if result:
                    queue_name, job_id = result
                    logger.info(f"Received job: {job_id}")
                    self.process_job(job_id)
                else:
                    logger.debug("No jobs in queue, continuing to poll...")
                    
            except KeyboardInterrupt:
                logger.info("Worker shutdown requested")
                break
            except Exception as e:
                logger.error(f"Worker error: {e}")
                time.sleep(5)  # Wait before retrying
        

def main():
    """Main entry point"""
    logger.info("Starting Mochi Video Generation Worker")
    
    # Initialize job processor
    processor = JobProcessor()
    
    # Test Redis connection
    try:
        processor.redis_client.ping()
        logger.info("Redis connection successful")
    except Exception as e:
        logger.error(f"Redis connection failed: {e}")
        return
    
    # Load Mochi pipeline
    try:
        processor.model_loader.load_model()
        logger.info("Mochi model loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load Mochi model: {e}")
        return
    
    # Start worker loop
    processor.worker_loop()

if __name__ == "__main__":
    main()


    