"""
Snapshot Manager - Captures and manages detection images
"""

import cv2
import numpy as np
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Dict
import json

logger = logging.getLogger(__name__)


class SnapshotManager:
    """Manages capture and storage of motion detection snapshots"""
    
    def __init__(self, config: dict):
        self.config = config
        self.snapshot_dir = Path('static/snapshots')
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        
        # Configuration
        self.save_interval = config.get('snapshots', {}).get('save_interval', 60)  # seconds
        self.max_snapshots = config.get('snapshots', {}).get('max_snapshots', 100)
        self.quality = config.get('snapshots', {}).get('quality', 85)
        
        self.last_snapshot_time = None
        
        logger.info(f"SnapshotManager initialized: interval={self.save_interval}s, max={self.max_snapshots}")
    
    def should_save_snapshot(self) -> bool:
        """Determine if a new snapshot should be saved"""
        if self.last_snapshot_time is None:
            return True
        
        elapsed = (datetime.now() - self.last_snapshot_time).seconds
        return elapsed >= self.save_interval
    
    def save_snapshot(
        self, 
        frame: np.ndarray, 
        motion_events: List,
        zones: List[Dict] = None
    ) -> Optional[Path]:
        """
        Save an annotated snapshot with motion detections
        
        Args:
            frame: Original video frame
            motion_events: List of MotionEvent objects
            zones: Optional list of zone definitions
            
        Returns:
            Path to saved snapshot or None
        """
        if not self.should_save_snapshot():
            return None
        
        if not motion_events:
            return None
        
        # Create annotated frame
        annotated = self._annotate_frame(frame.copy(), motion_events, zones)
        
        # Generate filename
        timestamp = datetime.now()
        filename = f"detection_{timestamp.strftime('%Y%m%d_%H%M%S')}.jpg"
        filepath = self.snapshot_dir / filename
        
        # Save image
        cv2.imwrite(
            str(filepath),
            annotated,
            [cv2.IMWRITE_JPEG_QUALITY, self.quality]
        )
        
        # Save metadata
        metadata = self._create_metadata(timestamp, motion_events, filename)
        metadata_path = self.snapshot_dir / f"{filename}.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2, default=str)
        
        self.last_snapshot_time = timestamp
        logger.info(f"📸 Snapshot saved: {filename}")
        
        # Cleanup old snapshots
        self._cleanup_old_snapshots()
        
        return filepath
    
    def _annotate_frame(
        self, 
        frame: np.ndarray, 
        motion_events: List,
        zones: List[Dict] = None
    ) -> np.ndarray:
        """Add annotations to frame"""
        # Draw zones first (background layer)
        if zones:
            for zone in zones:
                try:
                    color = eval(zone.get('color', '[0, 255, 0]'))
                    cv2.circle(
                        frame,
                        (zone['x'], zone['y']),
                        zone['radius'],
                        color,
                        2
                    )
                    cv2.putText(
                        frame,
                        zone['name'],
                        (zone['x'] - 30, zone['y'] - zone['radius'] - 10),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        color,
                        2
                    )
                except (KeyError, TypeError, ValueError, cv2.error) as e:
                    logger.exception("Failed to draw zone annotation for zone %r: %s", zone, e)
        
        # Draw motion detections
        for i, event in enumerate(motion_events):
            # Bounding box
            x, y, w, h = event.bounding_box
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
            
            # Centroid
            cv2.circle(frame, event.centroid, 5, (0, 0, 255), -1)
            
            # Info label
            label = f"#{i+1} Area: {event.area}"
            cv2.putText(
                frame,
                label,
                (x, y - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 255, 0),
                2
            )
        
        # Add timestamp
        timestamp_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cv2.putText(
            frame,
            timestamp_str,
            (10, frame.shape[0] - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            2
        )
        
        # Add detection count
        count_str = f"Detections: {len(motion_events)}"
        cv2.putText(
            frame,
            count_str,
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 0),
            2
        )
        
        return frame
    
    def _create_metadata(
        self, 
        timestamp: datetime, 
        motion_events: List,
        filename: str
    ) -> Dict:
        """Create metadata dictionary for snapshot"""
        return {
            'timestamp': timestamp.isoformat(),
            'filename': filename,
            'detection_count': len(motion_events),
            'detections': [
                {
                    'centroid': event.centroid,
                    'area': event.area,
                    'bounding_box': event.bounding_box,
                    'confidence': event.confidence
                }
                for event in motion_events
            ]
        }
    
    def _cleanup_old_snapshots(self):
        """Remove old snapshots exceeding max limit"""
        # Get all snapshot files (excluding metadata)
        snapshots = sorted(
            [f for f in self.snapshot_dir.glob('detection_*.jpg')],
            key=lambda x: x.stat().st_mtime,
            reverse=True
        )
        
        # Remove excess snapshots
        if len(snapshots) > self.max_snapshots:
            for snapshot in snapshots[self.max_snapshots:]:
                try:
                    snapshot.unlink()
                    # Also remove metadata
                    metadata_file = snapshot.with_suffix('.jpg.json')
                    if metadata_file.exists():
                        metadata_file.unlink()
                    logger.debug(f"Removed old snapshot: {snapshot.name}")
                except Exception as e:
                    logger.error(f"Error removing snapshot: {e}")
    
    def get_recent_snapshots(self, limit: int = 20) -> List[Dict]:
        """Get list of recent snapshots with metadata"""
        snapshots = sorted(
            self.snapshot_dir.glob('detection_*.jpg'),
            key=lambda x: x.stat().st_mtime,
            reverse=True
        )[:limit]
        
        result = []
        for snapshot in snapshots:
            metadata_file = snapshot.with_suffix('.jpg.json')
            metadata = {}
            
            if metadata_file.exists():
                try:
                    with open(metadata_file, 'r') as f:
                        metadata = json.load(f)
                except Exception as e:
                    logger.warning(f"Failed to load metadata from {metadata_file}: {e}")
            
            result.append({
                'filename': snapshot.name,
                'path': f'/static/snapshots/{snapshot.name}',
                'timestamp': datetime.fromtimestamp(snapshot.stat().st_mtime).isoformat(),
                'metadata': metadata
            })
        
        return result
    
    def get_snapshot_count(self) -> int:
        """Get total number of snapshots"""
        return len(list(self.snapshot_dir.glob('detection_*.jpg')))
