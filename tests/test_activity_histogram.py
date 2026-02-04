"""Tests for activity histogram bucketing"""

from datetime import datetime, timedelta

from src.database import Database


def _create_db(tmp_path):
    config = {
        'database': {
            'path': str(tmp_path / 'test_activity.db')
        }
    }
    return Database(config)


def test_activity_histogram_counts(tmp_path):
    db = _create_db(tmp_path)

    start = datetime(2026, 2, 3, 10, 0, 0)
    end = datetime(2026, 2, 3, 12, 0, 0)

    # Insert events at 10:05, 10:30, 11:15
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO motion_events (timestamp, centroid_x, centroid_y, area) VALUES (?, ?, ?, ?)",
            (start + timedelta(minutes=5), 10, 10, 1000)
        )
        cursor.execute(
            "INSERT INTO motion_events (timestamp, centroid_x, centroid_y, area) VALUES (?, ?, ?, ?)",
            (start + timedelta(minutes=30), 12, 12, 1200)
        )
        cursor.execute(
            "INSERT INTO motion_events (timestamp, centroid_x, centroid_y, area) VALUES (?, ?, ?, ?)",
            (start + timedelta(minutes=75), 12, 12, 1200)
        )

    buckets = db.get_activity_histogram(start, end, bucket_minutes=60)

    assert len(buckets) == 3
    assert buckets[0]['count'] == 2
    assert buckets[1]['count'] == 1
    assert buckets[2]['count'] == 0


def test_activity_histogram_empty_range(tmp_path):
    db = _create_db(tmp_path)

    start = datetime(2026, 2, 3, 10, 0, 0)
    end = datetime(2026, 2, 3, 10, 30, 0)

    buckets = db.get_activity_histogram(start, end, bucket_minutes=15)

    assert len(buckets) >= 1
    assert sum(bucket['count'] for bucket in buckets) == 0
