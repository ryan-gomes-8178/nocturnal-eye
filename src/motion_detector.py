"""
Motion Detector - OpenCV-based motion detection using background subtraction
"""

import cv2
import numpy as np
import logging
from typing import List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class MotionEvent:
    """Represents a detected motion event"""
    timestamp: datetime
    centroid: Tuple[int, int]  # (x, y)
    area: int
    bounding_box: Tuple[int, int, int, int]  # (x, y, w, h)
    confidence: float
    contour: np.ndarray = None
    track_id: Optional[int] = None


class MotionDetector:
    """Detects motion in video frames using background subtraction"""
    
    def __init__(self, config: dict):
        self.config = config
        
        # Motion detection parameters
        self.sensitivity = config['motion'].get('sensitivity', 16)
        self.min_area = config['motion'].get('min_area', 1000)
        self.max_area = config['motion'].get('max_area', 8000)
        self.history_frames = config['motion'].get('history_frames', 500)
        self.detect_shadows = config['motion'].get('detect_shadows', True)
        self.min_confidence = config['motion'].get('min_confidence', 0.0)
        
        # Region of Interest
        roi_config = config['motion'].get('region_of_interest', {})
        self.roi_enabled = roi_config.get('enabled', False)
        self.roi = None
        if self.roi_enabled:
            self.roi = (
                roi_config.get('x', 0),
                roi_config.get('y', 0),
                roi_config.get('width', 640),
                roi_config.get('height', 480)
            )
        
        # Initialize background subtractor
        self.bg_subtractor = cv2.createBackgroundSubtractorMOG2(
            history=self.history_frames,
            varThreshold=self.sensitivity,
            detectShadows=self.detect_shadows
        )
        
        # Tracking
        self.min_detections = config['tracking'].get('min_detections', 3)
        self.detection_buffer = []
        
        # Statistics
        self.frame_count = 0
        self.motion_count = 0
        
        logger.info(f"MotionDetector initialized: sensitivity={self.sensitivity}, "
                   f"min_area={self.min_area}, max_area={self.max_area}")
    
    def _apply_roi(self, frame: np.ndarray) -> np.ndarray:
        """Apply Region of Interest mask to frame"""
        if not self.roi_enabled or self.roi is None:
            return frame
        
        x, y, w, h = self.roi
        return frame[y:y+h, x:x+w]
    
    def _preprocess_frame(self, frame: np.ndarray) -> np.ndarray:
        """Preprocess frame for motion detection"""
        # Convert to grayscale if needed
        if len(frame.shape) == 3:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        else:
            gray = frame
        
        # Apply Gaussian blur to reduce noise
        blurred = cv2.GaussianBlur(gray, (21, 21), 0)
        
        return blurred
    
    def detect_motion(self, frame: np.ndarray) -> List[MotionEvent]:
        """
        Detect motion in the given frame
        
        Args:
            frame: Input video frame (BGR or grayscale)
            
        Returns:
            List of MotionEvent objects for detected motions
        """
        self.frame_count += 1
        
        if frame is None or frame.size == 0:
            logger.warning("Empty frame received")
            return []
        
        # Apply ROI if configured
        roi_frame = self._apply_roi(frame)
        
        # Preprocess
        processed = self._preprocess_frame(roi_frame)
        
        # Apply background subtraction
        fg_mask = self.bg_subtractor.apply(processed)
        
        # Remove shadows (they are marked as 127)
        if self.detect_shadows:
            _, fg_mask = cv2.threshold(fg_mask, 200, 255, cv2.THRESH_BINARY)
        
        # Morphological operations to remove noise
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, kernel)
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel)
        
        # Find contours
        contours, _ = cv2.findContours(
            fg_mask, 
            cv2.RETR_EXTERNAL, 
            cv2.CHAIN_APPROX_SIMPLE
        )
        
        # Process contours and create motion events
        motion_events = []
        
        for contour in contours:
            area = cv2.contourArea(contour)
            
            # Filter by area
            if not (self.min_area <= area <= self.max_area):
                continue
            
            # Calculate bounding box
            x, y, w, h = cv2.boundingRect(contour)
            
            # Adjust coordinates if ROI is used
            if self.roi_enabled and self.roi:
                x += self.roi[0]
                y += self.roi[1]
            
            # Calculate centroid
            M = cv2.moments(contour)
            if M['m00'] != 0:
                cx = int(M['m10'] / M['m00'])
                cy = int(M['m01'] / M['m00'])
                
                # Adjust centroid if ROI is used
                if self.roi_enabled and self.roi:
                    cx += self.roi[0]
                    cy += self.roi[1]
            else:
                cx = x + w // 2
                cy = y + h // 2
            
            # Calculate confidence based on area ratio
            confidence = min(1.0, area / self.max_area)

            # Filter by confidence threshold
            if confidence < self.min_confidence:
                continue
            
            # Create motion event
            event = MotionEvent(
                timestamp=datetime.now(),
                centroid=(cx, cy),
                area=int(area),
                bounding_box=(x, y, w, h),
                confidence=confidence,
                contour=contour
            )
            
            motion_events.append(event)
            self.motion_count += 1
        
        # Log motion detection
        if motion_events and self.frame_count % 10 == 0:
            logger.debug(f"Frame {self.frame_count}: {len(motion_events)} motion(s) detected")
        
        return motion_events
    
    def visualize_motion(self, frame: np.ndarray, motion_events: List[MotionEvent]) -> np.ndarray:
        """
        Draw motion detection visualization on frame
        
        Args:
            frame: Original frame
            motion_events: List of detected motion events
            
        Returns:
            Frame with visualization overlay
        """
        vis_frame = frame.copy()
        
        for event in motion_events:
            # Draw bounding box
            x, y, w, h = event.bounding_box
            cv2.rectangle(vis_frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
            
            # Draw centroid
            cv2.circle(vis_frame, event.centroid, 5, (0, 0, 255), -1)
            
            # Draw info text
            info_text = f"Area: {event.area}"
            cv2.putText(
                vis_frame, 
                info_text, 
                (x, y - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 255, 0),
                2
            )
        
        # Draw ROI if enabled
        if self.roi_enabled and self.roi:
            x, y, w, h = self.roi
            cv2.rectangle(vis_frame, (x, y), (x + w, y + h), (255, 0, 0), 2)
            cv2.putText(
                vis_frame,
                "ROI",
                (x + 5, y + 20),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 0, 0),
                2
            )
        
        # Draw stats
        stats_text = f"Frame: {self.frame_count} | Motions: {len(motion_events)} | Total: {self.motion_count}"
        cv2.putText(
            vis_frame,
            stats_text,
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2
        )
        
        return vis_frame
    
    def get_statistics(self) -> dict:
        """Get motion detection statistics"""
        return {
            'frames_processed': self.frame_count,
            'motions_detected': self.motion_count,
            'detection_rate': self.motion_count / max(1, self.frame_count)
        }
    
    def reset(self):
        """Reset the background model"""
        self.bg_subtractor = cv2.createBackgroundSubtractorMOG2(
            history=self.history_frames,
            varThreshold=self.sensitivity,
            detectShadows=self.detect_shadows
        )
        logger.info("Background model reset")


if __name__ == "__main__":
    # Test motion detector with webcam or video file
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Sample config
    config = {
        'motion': {
            'sensitivity': 16,
            'min_area': 1000,
            'max_area': 8000,
            'history_frames': 500,
            'detect_shadows': True,
            'region_of_interest': {
                'enabled': False
            }
        },
        'tracking': {
            'min_detections': 3
        }
    }
    
    detector = MotionDetector(config)
    
    # Test with webcam (0) or video file
    cap = cv2.VideoCapture(0)
    
    logger.info("Press 'q' to quit")
    
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            # Detect motion
            motion_events = detector.detect_motion(frame)
            
            # Visualize
            vis_frame = detector.visualize_motion(frame, motion_events)
            
            # Display
            cv2.imshow('Motion Detection', vis_frame)
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
                
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        cap.release()
        cv2.destroyAllWindows()
        
        # Print statistics
        stats = detector.get_statistics()
        logger.info(f"Statistics: {stats}")
