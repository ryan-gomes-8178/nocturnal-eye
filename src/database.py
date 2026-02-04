"""
Database - SQLite operations for activity logging
"""

import sqlite3
import logging
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class Database:
    """Manages SQLite database for gecko activity data"""
    
    def __init__(self, config: dict):
        self.config = config
        db_path = config['database'].get('path', 'data/gecko_activity.db')
        self.db_path = Path(db_path)
        
        # Ensure data directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize database
        self.init_database()
        
        logger.info(f"Database initialized: {self.db_path}")
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable column access by name
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            conn.close()
    
    def init_database(self):
        """Initialize database schema"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Motion events table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS motion_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME NOT NULL,
                    centroid_x INTEGER NOT NULL,
                    centroid_y INTEGER NOT NULL,
                    area INTEGER NOT NULL,
                    bbox_x INTEGER,
                    bbox_y INTEGER,
                    bbox_w INTEGER,
                    bbox_h INTEGER,
                    confidence REAL,
                    movement_vector TEXT,
                    zone_id INTEGER,
                    FOREIGN KEY (zone_id) REFERENCES zones(id)
                )
            ''')
            
            # Create index on timestamp for faster queries
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_motion_timestamp 
                ON motion_events(timestamp)
            ''')
            
            # Zones table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS zones (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    x INTEGER NOT NULL,
                    y INTEGER NOT NULL,
                    radius INTEGER NOT NULL,
                    color TEXT
                )
            ''')
            
            # Activity sessions table (grouped motion events)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS activity_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    start_time DATETIME NOT NULL,
                    end_time DATETIME,
                    duration_seconds INTEGER,
                    total_movements INTEGER DEFAULT 0,
                    avg_area REAL,
                    zones_visited TEXT
                )
            ''')
            
            # Daily statistics table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS daily_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date DATE NOT NULL UNIQUE,
                    total_movements INTEGER DEFAULT 0,
                    active_duration_seconds INTEGER DEFAULT 0,
                    most_active_hour INTEGER,
                    hotspot_x INTEGER,
                    hotspot_y INTEGER,
                    zones_visited TEXT
                )
            ''')
            
            logger.info("Database schema initialized")
    
    def insert_motion_event(self, event) -> int:
        """
        Insert a motion event into the database
        
        Args:
            event: MotionEvent object
            
        Returns:
            ID of inserted record
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO motion_events 
                (timestamp, centroid_x, centroid_y, area, bbox_x, bbox_y, bbox_w, bbox_h, confidence)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                event.timestamp,
                event.centroid[0],
                event.centroid[1],
                event.area,
                event.bounding_box[0],
                event.bounding_box[1],
                event.bounding_box[2],
                event.bounding_box[3],
                event.confidence
            ))
            
            return cursor.lastrowid
    
    def insert_motion_events_batch(self, events: List) -> int:
        """
        Insert multiple motion events in a batch
        
        Args:
            events: List of MotionEvent objects
            
        Returns:
            Number of records inserted
        """
        if not events:
            return 0
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            data = [
                (
                    event.timestamp,
                    event.centroid[0],
                    event.centroid[1],
                    event.area,
                    event.bounding_box[0],
                    event.bounding_box[1],
                    event.bounding_box[2],
                    event.bounding_box[3],
                    event.confidence
                )
                for event in events
            ]
            
            cursor.executemany('''
                INSERT INTO motion_events 
                (timestamp, centroid_x, centroid_y, area, bbox_x, bbox_y, bbox_w, bbox_h, confidence)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', data)
            
            return len(events)
    
    def get_events_by_date(self, date: datetime) -> List[Dict]:
        """Get all motion events for a specific date"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            start_date = date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = start_date + timedelta(days=1)
            
            cursor.execute('''
                SELECT * FROM motion_events
                WHERE timestamp >= ? AND timestamp < ?
                ORDER BY timestamp
            ''', (start_date, end_date))
            
            return [dict(row) for row in cursor.fetchall()]
    
    def get_events_by_range(self, start_date: datetime, end_date: datetime) -> List[Dict]:
        """Get motion events within a date range"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM motion_events
                WHERE timestamp >= ? AND timestamp < ?
                ORDER BY timestamp
            ''', (start_date, end_date))
            
            return [dict(row) for row in cursor.fetchall()]
    
    def get_latest_events(self, limit: int = 50) -> List[Dict]:
        """Get the most recent motion events"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM motion_events
                ORDER BY timestamp DESC
                LIMIT ?
            ''', (limit,))
            
            return [dict(row) for row in cursor.fetchall()]
    
    def get_daily_summary(self, date: datetime) -> Dict:
        """Get summary statistics for a specific date"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            start_date = date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = start_date + timedelta(days=1)
            
            cursor.execute('''
                SELECT 
                    COUNT(*) as total_events,
                    AVG(area) as avg_area,
                    AVG(centroid_x) as avg_x,
                    AVG(centroid_y) as avg_y,
                    MIN(timestamp) as first_event,
                    MAX(timestamp) as last_event
                FROM motion_events
                WHERE timestamp >= ? AND timestamp < ?
            ''', (start_date, end_date))
            
            result = cursor.fetchone()
            
            if result and result['total_events'] > 0:
                return {
                    'date': date.strftime('%Y-%m-%d'),
                    'total_events': result['total_events'],
                    'avg_area': round(result['avg_area'], 2) if result['avg_area'] else 0,
                    'center_of_activity': {
                        'x': round(result['avg_x'], 2) if result['avg_x'] else 0,
                        'y': round(result['avg_y'], 2) if result['avg_y'] else 0
                    },
                    'first_activity': result['first_event'],
                    'last_activity': result['last_event']
                }
            
            return {
                'date': date.strftime('%Y-%m-%d'),
                'total_events': 0,
                'message': 'No activity recorded'
            }
    
    def get_hourly_distribution(self, date: datetime) -> Dict[int, int]:
        """Get activity distribution by hour for a specific date"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            start_date = date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = start_date + timedelta(days=1)
            
            cursor.execute('''
                SELECT 
                    CAST(strftime('%H', timestamp) AS INTEGER) as hour,
                    COUNT(*) as count
                FROM motion_events
                WHERE timestamp >= ? AND timestamp < ?
                GROUP BY hour
                ORDER BY hour
            ''', (start_date, end_date))
            
            hourly_data = {row['hour']: row['count'] for row in cursor.fetchall()}
            
            # Fill in missing hours with 0
            return {hour: hourly_data.get(hour, 0) for hour in range(24)}

    def get_activity_histogram(
        self,
        start_date: datetime,
        end_date: datetime,
        bucket_minutes: int = 60,
    ) -> List[Dict]:
        """
        Get activity histogram for an arbitrary date range.

        Args:
            start_date: Start datetime for range
            end_date: End datetime for range
            bucket_minutes: Bucket size in minutes

        Returns:
            List of buckets with start/end and counts
        """
        if bucket_minutes <= 0:
            bucket_minutes = 60

        events = self.get_events_by_range(start_date, end_date)
        bucket_seconds = bucket_minutes * 60
        total_seconds = max(int((end_date - start_date).total_seconds()), 0)
        bucket_count = max(int(total_seconds // bucket_seconds) + 1, 1)

        buckets = [
            {
                'start': (start_date + timedelta(seconds=i * bucket_seconds)).isoformat(),
                'end': (start_date + timedelta(seconds=(i + 1) * bucket_seconds)).isoformat(),
                'count': 0,
            }
            for i in range(bucket_count)
        ]

        for event in events:
            event_time = event['timestamp']
            if isinstance(event_time, str):
                event_time = datetime.fromisoformat(event_time)
            delta_seconds = (event_time - start_date).total_seconds()
            if delta_seconds < 0:
                continue
            index = int(delta_seconds // bucket_seconds)
            if index >= bucket_count:
                continue
            buckets[index]['count'] += 1

        return buckets
    
    def get_heatmap_data(self, date: datetime, grid_size: int = 50) -> List[Tuple[int, int, int]]:
        """
        Get heatmap data for visualization
        
        Returns:
            List of (x, y, count) tuples
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            start_date = date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = start_date + timedelta(days=1)
            
            cursor.execute('''
                SELECT centroid_x, centroid_y
                FROM motion_events
                WHERE timestamp >= ? AND timestamp < ?
            ''', (start_date, end_date))
            
            points = [(row['centroid_x'], row['centroid_y']) for row in cursor.fetchall()]
            
            return points
    
    def insert_zone(self, name: str, x: int, y: int, radius: int, color: str = None) -> int:
        """Insert or update a zone definition"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO zones (name, x, y, radius, color)
                VALUES (?, ?, ?, ?, ?)
            ''', (name, x, y, radius, color or "[0, 255, 0]"))
            
            return cursor.lastrowid
    
    def get_zones(self) -> List[Dict]:
        """Get all defined zones"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM zones')
            return [dict(row) for row in cursor.fetchall()]
    
    def cleanup_old_data(self, days_to_keep: int = 30):
        """Remove data older than specified days"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)
            
            cursor.execute('''
                DELETE FROM motion_events
                WHERE timestamp < ?
            ''', (cutoff_date,))
            
            deleted = cursor.rowcount
            logger.info(f"Cleaned up {deleted} old records (older than {days_to_keep} days)")
            
            # Vacuum to reclaim space
            cursor.execute('VACUUM')
            
            return deleted
    
    def get_database_stats(self) -> Dict:
        """Get database statistics"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('SELECT COUNT(*) as count FROM motion_events')
            total_events = cursor.fetchone()['count']
            
            cursor.execute('SELECT COUNT(*) as count FROM zones')
            total_zones = cursor.fetchone()['count']
            
            cursor.execute('''
                SELECT MIN(timestamp) as first, MAX(timestamp) as last
                FROM motion_events
            ''')
            time_range = cursor.fetchone()
            
            db_size = self.db_path.stat().st_size if self.db_path.exists() else 0
            
            return {
                'total_events': total_events,
                'total_zones': total_zones,
                'first_event': time_range['first'],
                'last_event': time_range['last'],
                'database_size_mb': round(db_size / (1024 * 1024), 2)
            }


if __name__ == "__main__":
    # Test database operations
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    config = {
        'database': {
            'path': 'data/test_gecko_activity.db'
        }
    }
    
    db = Database(config)
    
    # Print stats
    stats = db.get_database_stats()
    logger.info(f"Database stats: {stats}")
    
    # Test zone insertion
    db.insert_zone("Test Zone", 100, 100, 50, "[255, 0, 0]")
    zones = db.get_zones()
    logger.info(f"Zones: {zones}")
