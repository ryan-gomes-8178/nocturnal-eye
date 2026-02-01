"""
Tracker - Object tracking and movement analysis
"""

import numpy as np
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from scipy.spatial import distance

logger = logging.getLogger(__name__)


@dataclass
class TrackedObject:
    """Represents a tracked object across frames"""
    track_id: int
    first_seen: datetime
    last_seen: datetime
    positions: List[Tuple[int, int]] = field(default_factory=list)
    areas: List[int] = field(default_factory=list)
    is_active: bool = True
    stationary_count: int = 0
    
    def update(self, centroid: Tuple[int, int], area: int, timestamp: datetime):
        """Update tracking with new position"""
        self.positions.append(centroid)
        self.areas.append(area)
        self.last_seen = timestamp
        
        # Check if stationary (within threshold)
        if len(self.positions) >= 2:
            last_pos = self.positions[-2]
            current_pos = self.positions[-1]
            dist = distance.euclidean(last_pos, current_pos)
            
            if dist < 10:  # pixels
                self.stationary_count += 1
            else:
                self.stationary_count = 0
    
    def get_average_position(self) -> Tuple[int, int]:
        """Calculate average position"""
        if not self.positions:
            return (0, 0)
        
        avg_x = sum(p[0] for p in self.positions) / len(self.positions)
        avg_y = sum(p[1] for p in self.positions) / len(self.positions)
        return (int(avg_x), int(avg_y))
    
    def get_movement_distance(self) -> float:
        """Calculate total movement distance"""
        if len(self.positions) < 2:
            return 0.0
        
        total_distance = 0.0
        for i in range(1, len(self.positions)):
            dist = distance.euclidean(self.positions[i-1], self.positions[i])
            total_distance += dist
        
        return total_distance
    
    def get_duration(self) -> timedelta:
        """Get tracking duration"""
        return self.last_seen - self.first_seen
    
    def is_stationary(self, threshold_frames: int = 30) -> bool:
        """Check if object has been stationary"""
        return self.stationary_count >= threshold_frames


class ObjectTracker:
    """Tracks objects across frames"""
    
    def __init__(self, config: dict):
        self.config = config
        self.max_tracking_distance = config['tracking'].get('max_tracking_distance', 100)
        self.stationary_threshold = config['tracking'].get('stationary_threshold', 5) * 60  # Convert minutes to seconds
        
        self.tracked_objects: Dict[int, TrackedObject] = {}
        self.next_track_id = 1
        self.inactive_timeout = timedelta(seconds=10)
        
        logger.info(f"ObjectTracker initialized: max_distance={self.max_tracking_distance}")
    
    def update(self, motion_events: List, timestamp: datetime) -> List[TrackedObject]:
        """
        Update tracking with new motion events
        
        Args:
            motion_events: List of MotionEvent objects
            timestamp: Current frame timestamp
            
        Returns:
            List of active tracked objects
        """
        # Mark all objects as potentially inactive
        for obj in self.tracked_objects.values():
            obj.is_active = False
        
        # Match motion events to existing tracks
        unmatched_events = []
        
        for event in motion_events:
            matched = False
            min_distance = float('inf')
            best_match_id = None
            
            # Find closest existing track
            for track_id, tracked_obj in self.tracked_objects.items():
                if not tracked_obj.positions:
                    continue
                
                last_pos = tracked_obj.positions[-1]
                dist = distance.euclidean(event.centroid, last_pos)
                
                if dist < self.max_tracking_distance and dist < min_distance:
                    min_distance = dist
                    best_match_id = track_id
                    matched = True
            
            # Update matched track
            if matched and best_match_id is not None:
                self.tracked_objects[best_match_id].update(
                    event.centroid,
                    event.area,
                    timestamp
                )
                self.tracked_objects[best_match_id].is_active = True
            else:
                unmatched_events.append(event)
        
        # Create new tracks for unmatched events
        for event in unmatched_events:
            new_track = TrackedObject(
                track_id=self.next_track_id,
                first_seen=timestamp,
                last_seen=timestamp,
                positions=[event.centroid],
                areas=[event.area]
            )
            self.tracked_objects[self.next_track_id] = new_track
            self.next_track_id += 1
        
        # Remove old inactive tracks
        self._cleanup_inactive_tracks(timestamp)
        
        return [obj for obj in self.tracked_objects.values() if obj.is_active]
    
    def _cleanup_inactive_tracks(self, current_time: datetime):
        """Remove tracks that have been inactive for too long"""
        to_remove = []
        
        for track_id, tracked_obj in self.tracked_objects.items():
            time_since_seen = current_time - tracked_obj.last_seen
            if time_since_seen > self.inactive_timeout:
                to_remove.append(track_id)
        
        for track_id in to_remove:
            del self.tracked_objects[track_id]
            logger.debug(f"Removed inactive track: {track_id}")
    
    def get_active_tracks(self) -> List[TrackedObject]:
        """Get all currently active tracks"""
        return [obj for obj in self.tracked_objects.values() if obj.is_active]
    
    def get_stationary_objects(self) -> List[TrackedObject]:
        """Get objects that are currently stationary"""
        return [
            obj for obj in self.tracked_objects.values()
            if obj.is_active and obj.is_stationary()
        ]
    
    def get_statistics(self) -> Dict:
        """Get tracking statistics"""
        active = self.get_active_tracks()
        stationary = self.get_stationary_objects()
        
        return {
            'total_tracks': len(self.tracked_objects),
            'active_tracks': len(active),
            'stationary_objects': len(stationary),
            'next_track_id': self.next_track_id
        }


class ZoneAnalyzer:
    """Analyzes activity within defined zones"""
    
    def __init__(self, zones: List[Dict]):
        self.zones = zones
        logger.info(f"ZoneAnalyzer initialized with {len(zones)} zones")
    
    def point_in_zone(self, point: Tuple[int, int], zone: Dict) -> bool:
        """Check if a point is within a zone (circular region)"""
        zone_center = (zone['x'], zone['y'])
        dist = distance.euclidean(point, zone_center)
        return dist <= zone['radius']
    
    def get_zone_for_position(self, position: Tuple[int, int]) -> Optional[str]:
        """Get the zone name for a given position"""
        for zone in self.zones:
            if self.point_in_zone(position, zone):
                return zone['name']
        return None
    
    def analyze_activity_by_zone(self, positions: List[Tuple[int, int]]) -> Dict[str, int]:
        """Count activity events per zone"""
        zone_counts = {zone['name']: 0 for zone in self.zones}
        zone_counts['Unknown'] = 0
        
        for position in positions:
            zone_name = self.get_zone_for_position(position)
            if zone_name:
                zone_counts[zone_name] += 1
            else:
                zone_counts['Unknown'] += 1
        
        return zone_counts
    
    def get_most_visited_zone(self, positions: List[Tuple[int, int]]) -> Optional[str]:
        """Determine the most visited zone"""
        zone_counts = self.analyze_activity_by_zone(positions)
        
        # Remove Unknown and find max
        if 'Unknown' in zone_counts:
            del zone_counts['Unknown']
        
        if not zone_counts:
            return None
        
        return max(zone_counts, key=zone_counts.get)


if __name__ == "__main__":
    # Test tracker
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    config = {
        'tracking': {
            'max_tracking_distance': 100,
            'stationary_threshold': 5
        }
    }
    
    tracker = ObjectTracker(config)
    
    # Test zone analyzer
    zones = [
        {'name': 'Zone A', 'x': 100, 'y': 100, 'radius': 50},
        {'name': 'Zone B', 'x': 300, 'y': 200, 'radius': 60},
    ]
    
    analyzer = ZoneAnalyzer(zones)
    
    # Test positions
    test_positions = [(105, 105), (102, 98), (300, 200), (400, 400)]
    zone_activity = analyzer.analyze_activity_by_zone(test_positions)
    logger.info(f"Zone activity: {zone_activity}")
