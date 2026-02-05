"""
Stream Consumer - Reads HLS streams from TerrariumPI
"""

import cv2
import numpy as np
import requests
import time
import logging
from typing import Optional, Generator
from pathlib import Path

logger = logging.getLogger(__name__)


class StreamConsumer:
    """Consumes HLS video streams and yields frames"""
    
    def __init__(self, config: dict):
        self.config = config
        self.stream_url = config['stream']['url']
        self.fallback_enabled = config['stream'].get('fallback_enabled', False)
        self.fallback_path = config['stream'].get('fallback_path', '')
        self.timeout = config['stream'].get('timeout', 30)
        self.max_retries = config['stream'].get('max_retries', 5)
        self.retry_delay = config['stream'].get('retry_delay', 10)
        self.retry_forever = config['stream'].get('retry_forever', False)
        self.fps_target = config['stream'].get('fps_target', 2)
        
        self.capture = None
        self.frame_count = 0
        self.last_frame_time = time.time()
        
    def connect(self) -> bool:
        """Connect to the video stream"""
        retries = 0
        
        # Disable retry_forever if fallback is enabled (they are mutually exclusive)
        effective_retry_forever = self.retry_forever and not self.fallback_enabled
        if self.retry_forever and self.fallback_enabled:
            logger.warning(
                "Both retry_forever and fallback are enabled. "
                "Disabling retry_forever to allow fallback mechanism to work. "
                f"Will retry up to {self.max_retries} times before using fallback."
            )

        while True:
            try:
                logger.info(f"Attempting to connect to stream: {self.stream_url}")
                
                # Try to connect to HLS stream
                self.capture = cv2.VideoCapture(self.stream_url)
                
                # Set timeout
                self.capture.set(cv2.CAP_PROP_BUFFERSIZE, 3)
                
                # Test if stream is valid
                ret, frame = self.capture.read()
                if ret and frame is not None:
                    logger.info("Successfully connected to stream")
                    return True
                else:
                    raise Exception("Failed to read frame from stream")
                    
            except Exception as e:
                retries += 1
                if effective_retry_forever:
                    logger.warning(f"Connection attempt {retries} failed: {e}")
                else:
                    logger.warning(f"Connection attempt {retries}/{self.max_retries} failed: {e}")
                
                if self.capture:
                    self.capture.release()
                    self.capture = None
                
                if effective_retry_forever or retries < self.max_retries:
                    logger.info(f"Retrying in {self.retry_delay} seconds...")
                    time.sleep(self.retry_delay)
                    continue

                break
        
        # Try fallback if enabled
        if self.fallback_enabled and self.fallback_path:
            logger.warning("Stream connection failed, trying fallback video file")
            return self._connect_fallback()
        
        logger.error("Failed to connect to stream after all retries")
        return False
    
    def _connect_fallback(self) -> bool:
        """Connect to fallback video file"""
        try:
            if not Path(self.fallback_path).exists():
                logger.error(f"Fallback video file not found: {self.fallback_path}")
                return False
            
            logger.info(f"Connecting to fallback video: {self.fallback_path}")
            self.capture = cv2.VideoCapture(self.fallback_path)
            
            ret, frame = self.capture.read()
            if ret and frame is not None:
                logger.info("Successfully connected to fallback video")
                return True
            else:
                logger.error("Failed to read fallback video")
                return False
                
        except Exception as e:
            logger.error(f"Fallback connection failed: {e}")
            return False
    
    def get_frames(self) -> Generator[np.ndarray, None, None]:
        """
        Generator that yields video frames
        Respects fps_target to limit processing rate
        """
        if not self.capture or not self.capture.isOpened():
            if not self.connect():
                logger.error("Cannot get frames: not connected")
                return
        
        frame_interval = 1.0 / self.fps_target if self.fps_target > 0 else 0
        
        while True:
            try:
                ret, frame = self.capture.read()
                
                if not ret or frame is None:
                    logger.warning("Failed to read frame, attempting to reconnect...")
                    self.close()
                    if not self.connect():
                        break
                    continue
                
                self.frame_count += 1
                
                # Frame rate limiting
                if frame_interval > 0:
                    elapsed = time.time() - self.last_frame_time
                    if elapsed < frame_interval:
                        time.sleep(frame_interval - elapsed)
                
                self.last_frame_time = time.time()
                
                # Log periodically
                if self.frame_count % 100 == 0:
                    logger.debug(f"Processed {self.frame_count} frames")
                
                yield frame
                
            except Exception as e:
                logger.error(f"Error reading frame: {e}")
                time.sleep(1)
                continue
    
    def get_frame_size(self) -> tuple:
        """Get the frame dimensions (width, height)"""
        if self.capture and self.capture.isOpened():
            width = int(self.capture.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(self.capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
            return (width, height)
        return (0, 0)
    
    def close(self):
        """Release the video capture"""
        if self.capture:
            self.capture.release()
            self.capture = None
            logger.info("Stream connection closed")
    
    def __enter__(self):
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def test_stream_connection(stream_url: str, duration: int = 10) -> bool:
    """
    Test stream connection and display frames
    
    Args:
        stream_url: URL of the HLS stream
        duration: Test duration in seconds
        
    Returns:
        True if connection successful
    """
    logger.info(f"Testing stream connection: {stream_url}")
    
    config = {
        'stream': {
            'url': stream_url,
            'timeout': 30,
            'max_retries': 3,
            'retry_delay': 5,
            'fps_target': 2
        }
    }
    
    consumer = StreamConsumer(config)
    
    if not consumer.connect():
        logger.error("Stream connection test failed")
        return False
    
    logger.info(f"Testing for {duration} seconds...")
    start_time = time.time()
    frame_count = 0
    
    try:
        for frame in consumer.get_frames():
            frame_count += 1
            
            # Display frame info
            if frame_count % 10 == 0:
                logger.info(f"Frame {frame_count}: {frame.shape}")
            
            # Check duration
            if time.time() - start_time > duration:
                break
                
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
    finally:
        consumer.close()
    
    logger.info(f"Test complete: {frame_count} frames processed")
    return True


if __name__ == "__main__":
    # Test the stream consumer
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Test with a sample URL (replace with your actual stream URL)
    test_url = "http://localhost:8090/webcam/1/stream.m3u8"
    test_stream_connection(test_url, duration=10)
