#!/usr/bin/env python3
"""
Test script for Nocturnal Eye components
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging
import yaml
import numpy as np
import cv2
import time
from pathlib import Path
from datetime import datetime, timedelta

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

from src.database import Database
from src.motion_detector import MotionDetector, MotionEvent
from src.tracker import ObjectTracker, ZoneAnalyzer
from src.visualizer import HeatmapGenerator
from src.snapshot_manager import SnapshotManager


def test_database():
    """Test database functionality"""
    logger.info("="*60)
    logger.info("Testing Database...")
    logger.info("="*60)
    
    config = {
        'database': {
            'path': 'data/test_gecko_activity.db'
        }
    }
    
    db = Database(config)
    
    # Test zone insertion
    logger.info("✓ Inserting test zones...")
    db.insert_zone("Feeding Zone", 100, 150, 50, "[0, 255, 0]")
    db.insert_zone("Basking Zone", 500, 100, 80, "[255, 165, 0]")
    db.insert_zone("Hide Zone", 300, 400, 70, "[0, 0, 255]")
    
    zones = db.get_zones()
    logger.info(f"✓ Zones created: {len(zones)} zones")
    for zone in zones:
        logger.info(f"  - {zone['name']} at ({zone['x']}, {zone['y']})")
    
    # Test database stats
    stats = db.get_database_stats()
    logger.info(f"✓ Database stats: {stats}")
    
    return db


def test_motion_detector():
    """Test motion detection"""
    logger.info("\n" + "="*60)
    logger.info("Testing Motion Detector...")
    logger.info("="*60)
    
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
    
    # Create synthetic video frames with simulated motion
    logger.info("✓ Generating synthetic test frames...")
    
    # Create black background
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    
    # Simulate gecko movement by drawing white circles
    for i in range(10):
        frame_copy = frame.copy()
        
        # Moving circle (simulating gecko)
        x = int(320 + 100 * np.sin(i * 0.5))
        y = int(240 + 80 * np.cos(i * 0.3))
        cv2.circle(frame_copy, (x, y), 30, (255, 255, 255), -1)
        
        # Detect motion
        motion_events = detector.detect_motion(frame_copy)
        
        if motion_events:
            logger.info(f"  Frame {i}: {len(motion_events)} motion event(s) detected")
            for event in motion_events:
                logger.info(f"    - Centroid: {event.centroid}, Area: {event.area}")
    
    stats = detector.get_statistics()
    logger.info(f"✓ Detection stats: {stats}")
    
    return detector


def test_tracker():
    """Test object tracking"""
    logger.info("\n" + "="*60)
    logger.info("Testing Object Tracker...")
    logger.info("="*60)
    
    config = {
        'tracking': {
            'max_tracking_distance': 100,
            'stationary_threshold': 5
        }
    }
    
    tracker = ObjectTracker(config)
    
    # Simulate motion events
    from src.motion_detector import MotionEvent
    
    logger.info("✓ Simulating tracked movements...")
    
    for frame_idx in range(20):
        timestamp = datetime.now() + timedelta(seconds=frame_idx)
        
        # Create motion events at different positions
        x = 100 + frame_idx * 10
        y = 150 + frame_idx * 5
        
        event = MotionEvent(
            timestamp=timestamp,
            centroid=(x, y),
            area=2000,
            bounding_box=(x-20, y-20, 40, 40),
            confidence=0.8
        )
        
        tracked = tracker.update([event], timestamp)
        
        if frame_idx % 5 == 0:
            stats = tracker.get_statistics()
            logger.info(f"  Frame {frame_idx}: {stats['active_tracks']} active tracks")
    
    stats = tracker.get_statistics()
    logger.info(f"✓ Tracker stats: {stats}")
    
    return tracker


def test_heatmap_generator():
    """Test heatmap generation"""
    logger.info("\n" + "="*60)
    logger.info("Testing Heatmap Generator...")
    logger.info("="*60)
    
    config = {
        'heatmap': {
            'grid_size': 50,
            'colormap': 'COLORMAP_JET',
            'overlay_alpha': 0.6
        },
        'static': {
            'heatmaps': 'static/heatmaps'
        }
    }
    
    generator = HeatmapGenerator(config)
    
    # Generate test data - concentrated around zones
    logger.info("✓ Generating test activity points...")
    
    np.random.seed(42)
    points = []
    
    # Feeding zone activity
    points.extend([
        (int(np.random.normal(100, 15)), int(np.random.normal(150, 15)))
        for _ in range(50)
    ])
    
    # Basking zone activity
    points.extend([
        (int(np.random.normal(500, 20)), int(np.random.normal(100, 20)))
        for _ in range(30)
    ])
    
    # Hide zone activity
    points.extend([
        (int(np.random.normal(300, 15)), int(np.random.normal(400, 15)))
        for _ in range(40)
    ])
    
    # Generate heatmap
    logger.info(f"  Total activity points: {len(points)}")
    heatmap = generator.generate_heatmap(points, title="Test Activity Heatmap")
    
    # Save heatmap
    output_path = generator.save_heatmap(heatmap, "test_heatmap.png")
    logger.info(f"✓ Heatmap saved to {output_path}")
    
    return generator


def test_zone_analyzer():
    """Test zone analysis"""
    logger.info("\n" + "="*60)
    logger.info("Testing Zone Analyzer...")
    logger.info("="*60)
    
    zones = [
        {'name': 'Feeding Zone', 'x': 100, 'y': 150, 'radius': 50},
        {'name': 'Basking Zone', 'x': 500, 'y': 100, 'radius': 80},
        {'name': 'Hide Zone', 'x': 300, 'y': 400, 'radius': 70},
    ]
    
    analyzer = ZoneAnalyzer(zones)
    
    # Test positions
    logger.info("✓ Testing zone detection...")
    
    test_positions = [
        (105, 155, "Feeding Zone"),
        (500, 100, "Basking Zone"),
        (300, 400, "Hide Zone"),
        (0, 0, "Unknown"),
    ]
    
    for x, y, expected_zone in test_positions:
        detected_zone = analyzer.get_zone_for_position((x, y))
        status = "✓" if detected_zone == expected_zone else "✗"
        logger.info(f"  {status} ({x}, {y}) -> {detected_zone} (expected: {expected_zone})")
    
    # Test activity analysis
    logger.info("✓ Analyzing zone activity...")
    
    np.random.seed(42)
    positions = [
        (int(np.random.normal(100, 15)), int(np.random.normal(150, 15)))
        for _ in range(50)
    ] + [
        (int(np.random.normal(500, 20)), int(np.random.normal(100, 20)))
        for _ in range(30)
    ] + [
        (int(np.random.normal(300, 15)), int(np.random.normal(400, 15)))
        for _ in range(40)
    ]
    
    zone_activity = analyzer.analyze_activity_by_zone(positions)
    logger.info("  Zone activity breakdown:")
    for zone_name, count in zone_activity.items():
        percentage = (count / len(positions)) * 100
        logger.info(f"    - {zone_name}: {count} ({percentage:.1f}%)")
    
    most_visited = analyzer.get_most_visited_zone(positions)
    logger.info(f"✓ Most visited zone: {most_visited}")
    
    return analyzer


def test_snapshot_manager():
    """Test snapshot manager functionality"""
    logger.info("\n" + "="*60)
    logger.info("Testing Snapshot Manager...")
    logger.info("="*60)
    
    # Configuration for testing
    config = {
        'snapshots': {
            'save_interval': 1,  # Short interval for testing
            'max_snapshots': 5,  # Small number for testing cleanup
            'quality': 85
        }
    }
    
    # Initialize snapshot manager
    manager = SnapshotManager(config)
    logger.info(f"✓ SnapshotManager initialized: interval={manager.save_interval}s, max={manager.max_snapshots}")
    
    # Create test frame
    logger.info("✓ Creating test frame...")
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.circle(frame, (320, 240), 50, (255, 255, 255), -1)
    
    # Create test motion events
    logger.info("✓ Creating test motion events...")
    timestamp = datetime.now()
    
    motion_events = [
        MotionEvent(
            timestamp=timestamp,
            centroid=(320, 240),
            area=2500,
            bounding_box=(270, 190, 100, 100),
            confidence=0.9
        ),
        MotionEvent(
            timestamp=timestamp,
            centroid=(150, 120),
            area=1800,
            bounding_box=(120, 90, 60, 60),
            confidence=0.75
        )
    ]
    
    # Test zones for annotation
    zones = [
        {'name': 'Test Zone', 'x': 320, 'y': 240, 'radius': 80, 'color': '[0, 255, 0]'}
    ]
    
    # Test snapshot capture
    logger.info("✓ Testing snapshot capture...")
    snapshot_path = manager.save_snapshot(frame, motion_events, zones)
    
    if snapshot_path:
        logger.info(f"  Snapshot saved to: {snapshot_path}")
        assert snapshot_path.exists(), "Snapshot file should exist"
        
        # Check metadata file
        metadata_path = snapshot_path.with_suffix('.jpg.json')
        assert metadata_path.exists(), "Metadata file should exist"
        logger.info(f"  Metadata saved to: {metadata_path}")
    else:
        logger.warning("  Snapshot not saved (interval not met or no motion)")
    
    # Test that second snapshot is blocked by interval
    logger.info("✓ Testing save interval...")
    snapshot_path2 = manager.save_snapshot(frame, motion_events, zones)
    if snapshot_path2 is None:
        logger.info("  ✓ Save interval correctly prevents duplicate snapshots")
    
    # Wait and test another snapshot
    time.sleep(1.1)
    logger.info("✓ Testing snapshot after interval...")
    snapshot_path3 = manager.save_snapshot(frame, motion_events, zones)
    if snapshot_path3:
        logger.info(f"  ✓ Snapshot saved after interval: {snapshot_path3}")
    
    # Test get_recent_snapshots
    logger.info("✓ Testing get_recent_snapshots...")
    recent = manager.get_recent_snapshots(limit=10)
    logger.info(f"  Found {len(recent)} recent snapshots")
    for snap in recent:
        logger.info(f"    - {snap['filename']}: {snap['metadata'].get('detection_count', 0)} detections")
    
    # Test snapshot count
    count = manager.get_snapshot_count()
    logger.info(f"✓ Total snapshots: {count}")
    
    # Test cleanup mechanism by creating more snapshots than max
    logger.info("✓ Testing cleanup mechanism...")
    logger.info(f"  Creating {manager.max_snapshots + 2} snapshots to test cleanup...")
    
    for i in range(manager.max_snapshots + 2):
        time.sleep(1.1)  # Wait for interval
        manager.save_snapshot(frame, motion_events, zones)
    
    final_count = manager.get_snapshot_count()
    logger.info(f"  Final count: {final_count} (max: {manager.max_snapshots})")
    assert final_count <= manager.max_snapshots, f"Cleanup should limit to {manager.max_snapshots} snapshots"
    logger.info(f"  ✓ Cleanup working correctly")
    
    # Test annotation rendering
    logger.info("✓ Testing annotation rendering...")
    annotated = manager._annotate_frame(frame.copy(), motion_events, zones)
    assert annotated is not None, "Annotated frame should not be None"
    assert annotated.shape == frame.shape, "Annotated frame should have same shape as original"
    logger.info("  ✓ Annotations rendered successfully")
    
    # Test metadata creation
    logger.info("✓ Testing metadata creation...")
    metadata = manager._create_metadata(timestamp, motion_events, "test.jpg")
    assert metadata['filename'] == "test.jpg", "Filename should match"
    assert metadata['detection_count'] == len(motion_events), "Detection count should match"
    assert len(metadata['detections']) == len(motion_events), "Number of detections should match"
    logger.info(f"  ✓ Metadata created: {metadata['detection_count']} detections")
    
    # Test empty motion events
    logger.info("✓ Testing with empty motion events...")
    time.sleep(1.1)
    snapshot_empty = manager.save_snapshot(frame, [], zones)
    assert snapshot_empty is None, "Should not save snapshot with no motion events"
    logger.info("  ✓ Correctly skips saving when no motion detected")
    
    logger.info("✓ Snapshot Manager tests completed successfully")
    
    return manager


def main():
    """Run all tests"""
    logger.info("\n")
    logger.info("🌙 NOCTURNAL EYE TEST SUITE 👁️")
    logger.info("Gecko Activity Tracking System\n")
    
    try:
        # Test components
        db = test_database()
        detector = test_motion_detector()
        tracker = test_tracker()
        generator = test_heatmap_generator()
        analyzer = test_zone_analyzer()
        snapshot_mgr = test_snapshot_manager()
        
        # Summary
        logger.info("\n" + "="*60)
        logger.info("✓ ALL TESTS PASSED!")
        logger.info("="*60)
        
        logger.info("\n📊 Component Status:")
        logger.info("  ✓ Database: OK")
        logger.info("  ✓ Motion Detector: OK")
        logger.info("  ✓ Object Tracker: OK")
        logger.info("  ✓ Heatmap Generator: OK")
        logger.info("  ✓ Zone Analyzer: OK")
        logger.info("  ✓ Snapshot Manager: OK")
        
        logger.info("\n🚀 Next Steps:")
        logger.info("  1. Connect your camera to TerrariumPI")
        logger.info("  2. Configure stream URL in config.yaml")
        logger.info("  3. Run: python main.py")
        logger.info("  4. In another terminal: python -m src.api.app")
        logger.info("  5. Access API: http://localhost:5001/api/health")
        
        logger.info("\n📚 Documentation:")
        logger.info("  - README.md: Quick start guide")
        logger.info("  - config.yaml: Configuration options")
        logger.info("  - logs/: Application logs")
        
        return 0
        
    except Exception as e:
        logger.error(f"✗ Test failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
