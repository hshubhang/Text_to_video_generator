import os
import torch
import logging
from diffusers import MochiPipeline
from diffusers.utils import export_to_video

logger = logging.getLogger(__name__)

class MochiModelLoader:
    def __init__(self, model_path="/app/model-weights/mochi-1-preview/"):
        self.model_path = model_path
        self.pipeline = None
        
    def load_model(self):
        """Load Mochi pipeline once on startup"""
        logger.info(f"Loading Mochi pipeline from {self.model_path}")
        
        self.pipeline = MochiPipeline.from_pretrained(
            self.model_path,
            torch_dtype=torch.bfloat16,
            device_map="balanced"
        )
        
        logger.info("Mochi pipeline loaded successfully")
        return self.pipeline
    
    def generate_video(self, prompt, duration=10, resolution="480p", fps=8):
        """Generate video from text prompt"""
        if self.pipeline is None:
            raise RuntimeError("Model not loaded. Call load_model() first.")
            
        logger.info(f"Generating video: '{prompt}' ({duration}s, {fps}fps, {resolution})")
        
        # Parse resolution
        height, width = self._parse_resolution(resolution)
        
        # Generate frames
        frames = self.pipeline(
            prompt=prompt,
            height=height,
            width=width, 
            num_frames=duration * fps,  # Use configurable fps
            num_inference_steps=64
        ).frames[0]
        
        return frames
    
    def _parse_resolution(self, resolution):
        """Parse resolution string to height, width"""
        res_map = {
            "480p": (480, 848),
            "720p": (720, 1280), 
            "1080p": (1080, 1920)
        }
        return res_map.get(resolution, (480, 848))