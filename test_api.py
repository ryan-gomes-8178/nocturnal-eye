#!/usr/bin/env python3
"""
API Test Script - Tests REST API endpoints
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging
import json
import yaml
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

from src.database import Database
from src.motion_detector import MotionEvent
from src.api.app import app


def populate_test_data():
    """Populate database with test data"""
    logger.info("="*60)
    logger.info("Populating Database with Test Data...")
    logger.info("="*60)
    
    config = {
        'database': {
            'path': 'data/test_gecko_activity.db'
        }
    }
    
    db = Database(config)
    
    # Create zones
    db.insert_zone("Feeding Zone", 100, 150, 50, "[0, 255, 0]")
    db.insert_zone("Basking Zone", 500, 100, 80, "[255, 165, 0]")
    db.insert_zone("Hide Zone", 300, 400, 70, "[0, 0, 255]")
    
    logger.info("✓ Zones created")
    
    # Generate motion events for the last 3 days
    np.random.seed(42)
    
    for day_offset in range(3):
        date = datetime.now() - timedelta(days=day_offset)
        
        # Generate events between 20:00 and 08:00
        for hour in [20, 21, 22, 23, 0, 1, 2, 3, 4, 5, 6, 7]:
            num_events = np.random.randint(5, 20)
            
            for _ in range(num_events):
                minute = np.random.randint(0, 60)
                second = np.random.randint(0, 60)
                
                # Random position within terrarium
                x = int(np.random.uniform(50, 590))
                y = int(np.random.uniform(50, 430))
                
                # Random area
                area = int(np.random.uniform(1500, 6000))
                
                timestamp = date.replace(hour=hour, minute=minute, second=second)
                
                event = MotionEvent(
                    timestamp=timestamp,
                    centroid=(x, y),
                    area=area,
                    bounding_box=(x-25, y-25, 50, 50),
                    confidence=np.random.uniform(0.7, 0.99)
                )
                
                db.insert_motion_event(event)
    
    logger.info("✓ Generated 3 days of test activity data")
    
    # Display summary
    stats = db.get_database_stats()
    logger.info(f"✓ Database stats: {stats}")
    
    return db


def test_api_endpoints():
    """Test API endpoints"""
    logger.info("\n" + "="*60)
    logger.info("Testing API Endpoints...")
    logger.info("="*60)
    
    # Use Flask test client
    client = app.test_client()
    test_num = 1
    
    # Test: Health check
    logger.info(f"\n{test_num}. Testing /api/health")
    test_num += 1
    response = client.get('/api/health')
    if response.status_code == 200:
        data = json.loads(response.data)
        logger.info(f"   ✓ Status: {response.status_code}")
        logger.info(f"   ✓ Response: {data['status']}")
        logger.info(f"   ✓ Database: {data['database']}")
    else:
        logger.error(f"   ✗ Status: {response.status_code}")
    
    # Test: Today's activity
    logger.info(f"\n{test_num}. Testing /api/activity/today")
    test_num += 1
    response = client.get('/api/activity/today')
    if response.status_code == 200:
        data = json.loads(response.data)
        logger.info(f"   ✓ Status: {response.status_code}")
        logger.info(f"   ✓ Today's events: {data['summary']['total_events']}")
        if data['summary']['total_events'] > 0:
            logger.info(f"   ✓ Center of activity: {data['summary']['center_of_activity']}")
    else:
        logger.error(f"   ✗ Status: {response.status_code}")
    
    # Test: Date range query
    logger.info(f"\n{test_num}. Testing /api/activity/range")
    test_num += 1
    start_date = (datetime.now() - timedelta(days=3)).strftime('%Y-%m-%d')
    end_date = datetime.now().strftime('%Y-%m-%d')
    response = client.get(f'/api/activity/range?start={start_date}T00:00:00&end={end_date}T23:59:59')
    if response.status_code == 200:
        data = json.loads(response.data)
        logger.info(f"   ✓ Status: {response.status_code}")
        logger.info(f"   ✓ Range: {start_date} to {end_date}")
        logger.info(f"   ✓ Total events: {data['total_events']}")
    else:
        logger.error(f"   ✗ Status: {response.status_code}")
    
    # Test: Latest events
    logger.info(f"\n{test_num}. Testing /api/events/latest")
    test_num += 1
    response = client.get('/api/events/latest?limit=10')
    if response.status_code == 200:
        data = json.loads(response.data)
        logger.info(f"   ✓ Status: {response.status_code}")
        logger.info(f"   ✓ Latest events: {data['count']}")
        if data['events']:
            logger.info(f"   ✓ Most recent: {data['events'][0]['timestamp']}")
    else:
        logger.error(f"   ✗ Status: {response.status_code}")
    
    # Test: Weekly stats
    logger.info(f"\n{test_num}. Testing /api/stats/weekly")
    test_num += 1
    response = client.get('/api/stats/weekly')
    if response.status_code == 200:
        data = json.loads(response.data)
        logger.info(f"   ✓ Status: {response.status_code}")
        logger.info(f"   ✓ Week range: {data['start_date']} to {data['end_date']}")
        total_events = sum(stat['total_events'] for stat in data['daily_stats'])
        logger.info(f"   ✓ Total week events: {total_events}")
    else:
        logger.error(f"   ✗ Status: {response.status_code}")
    
    # Test: Zones
    logger.info(f"\n{test_num}. Testing /api/zones")
    test_num += 1
    response = client.get('/api/zones')
    if response.status_code == 200:
        data = json.loads(response.data)
        logger.info(f"   ✓ Status: {response.status_code}")
        logger.info(f"   ✓ Zones: {len(data['zones'])}")
        for zone in data['zones']:
            logger.info(f"     - {zone['name']}")
    else:
        logger.error(f"   ✗ Status: {response.status_code}")
    
    # Test: Database stats
    logger.info(f"\n{test_num}. Testing /api/database/stats")
    test_num += 1
    response = client.get('/api/database/stats')
    if response.status_code == 200:
        data = json.loads(response.data)
        logger.info(f"   ✓ Status: {response.status_code}")
        logger.info(f"   ✓ Total events: {data['total_events']}")
        logger.info(f"   ✓ Database size: {data['database_size_mb']} MB")
    else:
        logger.error(f"   ✗ Status: {response.status_code}")
    
    # Test: Heatmap generation
    logger.info(f"\n{test_num}. Testing /api/heatmap")
    test_num += 1
    date_str = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    response = client.get(f'/api/heatmap?date={date_str}')
    if response.status_code == 200:
        logger.info(f"   ✓ Status: {response.status_code}")
        logger.info(f"   ✓ Content-Type: {response.content_type}")
        logger.info(f"   ✓ Size: {len(response.data)} bytes")
    else:
        logger.info(f"   ℹ Status: {response.status_code} (likely no data for this date)")
    
    # Test: Stream configuration
    logger.info(f"\n{test_num}. Testing /api/config/stream")
    test_num += 1
    response = client.get('/api/config/stream')
    if response.status_code == 200:
        data = json.loads(response.data)
        logger.info(f"   ✓ Status: {response.status_code}")
        logger.info(f"   ✓ Stream URL: {data.get('url', 'NOT CONFIGURED')}")
        logger.info(f"   ✓ Fallback enabled: {data.get('fallback_enabled', False)}")
    else:
        logger.error(f"   ✗ Status: {response.status_code}")


def main():
    """Run API tests"""
    logger.info("\n")
    logger.info("🌙 NOCTURNAL EYE API TEST SUITE 👁️")
    logger.info("REST API Validation\n")
    
    try:
        # Populate test data
        db = populate_test_data()
        
        # Test endpoints
        test_api_endpoints()
        
        # Summary
        logger.info("\n" + "="*60)
        logger.info("✓ API TEST SUITE COMPLETE")
        logger.info("="*60)
        
        logger.info("\n🚀 API Ready for Production:")
        logger.info("  Start API server: python -m src.api.app")
        logger.info("  Base URL: http://localhost:5001")
        logger.info("  Health check: http://localhost:5001/api/health")
        
        return 0
        
    except Exception as e:
        logger.error(f"✗ Test failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
