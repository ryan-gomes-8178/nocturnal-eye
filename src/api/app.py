"""
Flask API - REST API for accessing gecko activity data
"""

from flask import Flask, jsonify, request, send_file, send_from_directory
from flask_cors import CORS
import logging
from datetime import datetime, timedelta
from pathlib import Path
import yaml

from src.database import Database
from src.visualizer import HeatmapGenerator, ActivityVisualizer
from src.snapshot_manager import SnapshotManager

logger = logging.getLogger(__name__)

# Load config
with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)

# Initialize Flask app
app = Flask(__name__, static_folder='../../static', static_url_path='/static')
allowed_origins = config.get('allowed_cors_origins', ['http://localhost:5001'])
CORS(app, origins=allowed_origins)

# Initialize components
db = Database(config)
heatmap_gen = HeatmapGenerator(config)
activity_viz = ActivityVisualizer(config)
snapshot_mgr = SnapshotManager(config)


@app.route('/')
def dashboard():
    """Serve the dashboard"""
    return send_from_directory(app.static_folder, 'dashboard.html')


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        stats = db.get_database_stats()
        return jsonify({
            'status': 'healthy',
            'database': 'connected',
            'stats': stats
        })
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 500


@app.route('/api/activity/today', methods=['GET'])
def get_today_activity():
    """Get today's activity summary"""
    try:
        today = datetime.now()
        summary = db.get_daily_summary(today)
        hourly = db.get_hourly_distribution(today)
        
        return jsonify({
            'summary': summary,
            'hourly_distribution': hourly
        })
    except Exception as e:
        logger.error(f"Error getting today's activity: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/activity/range', methods=['GET'])
def get_activity_range():
    """Get activity data for a date range"""
    try:
        start_str = request.args.get('start')
        end_str = request.args.get('end')
        
        if not start_str or not end_str:
            return jsonify({'error': 'Missing start or end parameter'}), 400
        
        start_date = datetime.fromisoformat(start_str)
        end_date = datetime.fromisoformat(end_str)
        
        events = db.get_events_by_range(start_date, end_date)
        
        return jsonify({
            'start_date': start_str,
            'end_date': end_str,
            'total_events': len(events),
            'events': events[:100]  # Limit to 100 for response size
        })
    except ValueError as e:
        return jsonify({'error': f'Invalid date format: {e}'}), 400
    except Exception as e:
        logger.error(f"Error getting activity range: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/events/latest', methods=['GET'])
def get_latest_events():
    """Get the most recent motion events"""
    try:
        limit = int(request.args.get('limit', 50))
        limit = min(limit, 500)  # Max 500
        
        events = db.get_latest_events(limit)
        
        return jsonify({
            'count': len(events),
            'events': events
        })
    except Exception as e:
        logger.error(f"Error getting latest events: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/heatmap', methods=['GET'])
def get_heatmap():
    """Generate and return a heatmap image"""
    try:
        date_str = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
        date = datetime.fromisoformat(date_str)
        
        # Check if heatmap already exists
        filename = f"heatmap_{date_str}.png"
        heatmap_path = heatmap_gen.output_dir / filename
        
        if not heatmap_path.exists():
            # Generate new heatmap
            points = db.get_heatmap_data(date)
            
            if not points:
                return jsonify({'error': 'No data available for this date'}), 404
            
            heatmap = heatmap_gen.generate_heatmap(
                points,
                title=f"Activity Heatmap - {date_str}"
            )
            heatmap_path = heatmap_gen.save_heatmap(heatmap, filename, date)
        
        return send_file(heatmap_path, mimetype='image/png')
        
    except ValueError as e:
        return jsonify({'error': f'Invalid date format: {e}'}), 400
    except Exception as e:
        logger.error(f"Error generating heatmap: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/stats/weekly', methods=['GET'])
def get_weekly_stats():
    """Get weekly statistics"""
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)
        
        daily_stats = []
        for i in range(7):
            date = start_date + timedelta(days=i)
            summary = db.get_daily_summary(date)
            daily_stats.append(summary)
        
        return jsonify({
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d'),
            'daily_stats': daily_stats
        })
    except Exception as e:
        logger.error(f"Error getting weekly stats: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/zones', methods=['GET'])
def get_zones():
    """Get all defined zones"""
    try:
        zones = db.get_zones()
        return jsonify({'zones': zones})
    except Exception as e:
        logger.error(f"Error getting zones: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/zones', methods=['POST'])
def create_zone():
    """Create a new zone"""
    try:
        data = request.json
        
        required_fields = ['name', 'x', 'y', 'radius']
        if not all(field in data for field in required_fields):
            return jsonify({'error': 'Missing required fields'}), 400
        
        zone_id = db.insert_zone(
            data['name'],
            data['x'],
            data['y'],
            data['radius'],
            data.get('color', '[0, 255, 0]')
        )
        
        return jsonify({
            'message': 'Zone created successfully',
            'zone_id': zone_id
        }), 201
        
    except Exception as e:
        logger.error(f"Error creating zone: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/database/stats', methods=['GET'])
def get_database_stats():
    """Get database statistics"""
    try:
        stats = db.get_database_stats()
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Error getting database stats: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/database/cleanup', methods=['POST'])
def cleanup_database():
    """Cleanup old database records"""
    try:
        days = int(request.json.get('days_to_keep', 30))
        deleted = db.cleanup_old_data(days)
        
        return jsonify({
            'message': 'Cleanup successful',
            'records_deleted': deleted
        })
    except Exception as e:
        logger.error(f"Error cleaning database: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/snapshots/recent', methods=['GET'])
def get_recent_snapshots():
    """Get recent detection snapshots"""
    try:
        limit_param = request.args.get('limit', '20')
        offset_param = request.args.get('offset', '0')
        try:
            limit = int(limit_param)
            offset = int(offset_param)
        except (TypeError, ValueError):
            return jsonify({'error': 'Invalid limit/offset parameter. It must be an integer.'}), 400

        if limit <= 0 or offset < 0:
            return jsonify({'error': 'Invalid limit/offset parameter.'}), 400

        limit = min(limit, 500)
        snapshots = snapshot_mgr.get_snapshots_paginated(offset=offset, limit=limit)
        
        return jsonify({
            'count': len(snapshots),
            'offset': offset,
            'limit': limit,
            'snapshots': snapshots
        })
    except Exception as e:
        logger.error(f"Error getting snapshots: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/snapshots/range', methods=['GET'])
def get_snapshots_range():
    """Get detection snapshots within a time range"""
    try:
        start_str = request.args.get('start')
        end_str = request.args.get('end')
        if not start_str or not end_str:
            return jsonify({'error': 'Missing start or end parameter'}), 400

        limit_param = request.args.get('limit', '50')
        offset_param = request.args.get('offset', '0')
        try:
            limit = int(limit_param)
            offset = int(offset_param)
        except (TypeError, ValueError):
            return jsonify({'error': 'Invalid limit/offset parameter. It must be an integer.'}), 400

        if limit <= 0 or offset < 0:
            return jsonify({'error': 'Invalid limit/offset parameter.'}), 400

        limit = min(limit, 500)
        start_date = datetime.fromisoformat(start_str)
        end_date = datetime.fromisoformat(end_str)

        data = snapshot_mgr.get_snapshots_in_range(start_date, end_date, offset=offset, limit=limit)

        return jsonify({
            'total': data['total'],
            'count': len(data['snapshots']),
            'offset': offset,
            'limit': limit,
            'start': start_str,
            'end': end_str,
            'snapshots': data['snapshots']
        })
    except ValueError as e:
        return jsonify({'error': f'Invalid date format: {e}'}), 400
    except Exception as e:
        logger.error(f"Error getting snapshot range: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/snapshots/count', methods=['GET'])
def get_snapshot_count():
    """Get total number of snapshots"""
    try:
        count = snapshot_mgr.get_snapshot_count()
        return jsonify({'count': count})
    except Exception as e:
        logger.error(f"Error getting snapshot count: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/dashboard/summary', methods=['GET'])
def get_dashboard_summary():
    """Get complete dashboard summary"""
    try:
        # Today's activity
        today = datetime.now()
        daily_summary = db.get_daily_summary(today)
        hourly_dist = db.get_hourly_distribution(today)
        
        # Recent snapshots
        recent_snapshots = snapshot_mgr.get_recent_snapshots(10)
        
        # Database stats
        db_stats = db.get_database_stats()
        
        # Zones
        zones = db.get_zones()
        
        return jsonify({
            'daily_summary': daily_summary,
            'hourly_distribution': hourly_dist,
            'recent_snapshots': recent_snapshots,
            'database_stats': db_stats,
            'zones': zones,
            'snapshot_count': snapshot_mgr.get_snapshot_count()
        })
    except Exception as e:
        logger.error(f"Error getting dashboard summary: {e}")
        return jsonify({'error': str(e)}), 500


def run_api_server():
    """Run the Flask API server"""
    api_config = config.get('api', {})
    
    if not api_config.get('enabled', True):
        logger.info("API server is disabled in configuration")
        return
    
    host = api_config.get('host', '0.0.0.0')
    port = api_config.get('port', 5001)
    debug = api_config.get('debug', False)
    
    logger.info(f"🚀 Starting API server on {host}:{port}")
    
    app.run(
        host=host,
        port=port,
        debug=debug,
        threaded=True
    )


if __name__ == '__main__':
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    run_api_server()
