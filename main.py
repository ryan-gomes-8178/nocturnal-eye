"""
Main Application - Nocturnal Eye Gecko Tracking System
"""

import sys
import signal
import logging
import argparse
import yaml
from pathlib import Path
from datetime import datetime, time as dt_time
from time import sleep
import colorlog

from src.stream_consumer import StreamConsumer
from src.motion_detector import MotionDetector
from src.database import Database
from src.tracker import ObjectTracker, ZoneAnalyzer
from src.visualizer import HeatmapGenerator


class NocturnalEye:
    """Main application class"""
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config = self.load_config(config_path)
        self.setup_logging()
        self.running = False
        
        # Initialize components
        logger.info("Initializing Nocturnal Eye...")
        
        try:
            self.database = Database(self.config)
            self.stream_consumer = StreamConsumer(self.config)
            self.motion_detector = MotionDetector(self.config)
            self.tracker = ObjectTracker(self.config)
            self.heatmap_generator = HeatmapGenerator(self.config)
            
            # Load zones from database
            zones = self.database.get_zones()
            if not zones and self.config.get('zones'):
                # Initialize zones from config
                for zone in self.config['zones']:
                    self.database.insert_zone(
                        zone['name'],
                        zone['x'],
                        zone['y'],
                        zone['radius'],
                        str(zone.get('color', [0, 255, 0]))
                    )
                zones = self.database.get_zones()
            
            self.zone_analyzer = ZoneAnalyzer(zones) if zones else None
            
            logger.info("✓ All components initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize components: {e}")
            raise
    
    def load_config(self, config_path: str) -> dict:
        """Load configuration from YAML file"""
        config_file = Path(config_path)
        
        if not config_file.exists():
            logger.error(f"Config file not found: {config_path}")
            sys.exit(1)
        
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
        
        return config
    
    def setup_logging(self):
        """Setup logging configuration"""
        log_config = self.config.get('logging', {})
        log_level = getattr(logging, log_config.get('level', 'INFO'))
        log_file = log_config.get('file', 'logs/nocturnal_eye.log')
        console_enabled = log_config.get('console', True)
        
        # Ensure log directory exists
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        
        # Create formatters
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        console_formatter = colorlog.ColoredFormatter(
            '%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            log_colors={
                'DEBUG': 'cyan',
                'INFO': 'green',
                'WARNING': 'yellow',
                'ERROR': 'red',
                'CRITICAL': 'red,bg_white',
            }
        )
        
        # Setup root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(log_level)
        
        # Remove existing handlers
        root_logger.handlers = []
        
        # File handler
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(log_level)
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)
        
        # Console handler
        if console_enabled:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(log_level)
            console_handler.setFormatter(console_formatter)
            root_logger.addHandler(console_handler)
        
        global logger
        logger = logging.getLogger(__name__)
    
    def is_within_schedule(self) -> bool:
        """Check if current time is within monitoring schedule"""
        schedule_config = self.config.get('schedule', {})
        
        if not schedule_config.get('enabled', True):
            return True
        
        now = datetime.now().time()
        start_time = dt_time.fromisoformat(schedule_config.get('start_time', '20:00'))
        end_time = dt_time.fromisoformat(schedule_config.get('end_time', '08:00'))
        
        # Handle overnight schedule (e.g., 20:00 to 08:00)
        if start_time > end_time:
            return now >= start_time or now <= end_time
        else:
            return start_time <= now <= end_time
    
    def run(self):
        """Main run loop"""
        logger.info("🌙 Nocturnal Eye starting up...")
        logger.info(f"Configuration: {Path(self.config.get('database', {}).get('path', 'N/A'))}")
        
        self.running = True
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        try:
            # Connect to stream
            if not self.stream_consumer.connect():
                logger.error("Failed to connect to stream. Exiting.")
                return
            
            logger.info("✓ Connected to video stream")
            
            # Get frame size for heatmap generation
            frame_size = self.stream_consumer.get_frame_size()
            logger.info(f"Frame size: {frame_size[0]}x{frame_size[1]}")
            
            # Main processing loop
            frame_count = 0
            last_stats_time = datetime.now()
            batch_events = []
            
            for frame in self.stream_consumer.get_frames():
                if not self.running:
                    break
                
                frame_count += 1
                current_time = datetime.now()
                
                # Check schedule
                if not self.is_within_schedule():
                    if frame_count % 300 == 0:  # Log every 5 minutes at 1 FPS
                        logger.info("Outside monitoring schedule, skipping processing")
                    sleep(1)
                    continue
                
                # Detect motion
                motion_events = self.motion_detector.detect_motion(frame)
                
                if motion_events:
                    # Update tracker
                    tracked_objects = self.tracker.update(motion_events, current_time)
                    
                    # Add to batch for database insertion
                    batch_events.extend(motion_events)
                    
                    # Log active tracking
                    if len(tracked_objects) > 0:
                        logger.info(f"🦎 Active: {len(tracked_objects)} gecko(s) detected")
                
                # Batch insert to database every 10 events
                if len(batch_events) >= 10:
                    self.database.insert_motion_events_batch(batch_events)
                    batch_events = []
                
                # Periodic statistics logging
                if (current_time - last_stats_time).seconds >= 300:  # Every 5 minutes
                    self._log_statistics()
                    last_stats_time = current_time
                
        except KeyboardInterrupt:
            logger.info("\n⏸️  Interrupted by user")
        except Exception as e:
            logger.error(f"Error in main loop: {e}", exc_info=True)
        finally:
            # Insert any remaining events
            if batch_events:
                self.database.insert_motion_events_batch(batch_events)
            
            self.shutdown()
    
    def _log_statistics(self):
        """Log periodic statistics"""
        motion_stats = self.motion_detector.get_statistics()
        tracker_stats = self.tracker.get_statistics()
        db_stats = self.database.get_database_stats()
        
        logger.info("📊 Statistics:")
        logger.info(f"  Frames: {motion_stats['frames_processed']}")
        logger.info(f"  Motions: {motion_stats['motions_detected']}")
        logger.info(f"  Active tracks: {tracker_stats['active_tracks']}")
        logger.info(f"  Database events: {db_stats['total_events']}")
        logger.info(f"  Database size: {db_stats['database_size_mb']} MB")
    
    def signal_handler(self, signum, frame):
        """Handle termination signals"""
        logger.info(f"\n🛑 Received signal {signum}, shutting down...")
        self.running = False
    
    def shutdown(self):
        """Cleanup and shutdown"""
        logger.info("🔌 Shutting down Nocturnal Eye...")
        
        try:
            self.stream_consumer.close()
            logger.info("✓ Stream consumer closed")
            
            # Final statistics
            self._log_statistics()
            
            # Generate end-of-session heatmap
            today = datetime.now()
            events = self.database.get_events_by_date(today)
            if events:
                points = [(e['centroid_x'], e['centroid_y']) for e in events]
                heatmap = self.heatmap_generator.generate_heatmap(
                    points,
                    title=f"Activity Heatmap - {today.strftime('%Y-%m-%d')}"
                )
                self.heatmap_generator.save_heatmap(heatmap, date=today)
                logger.info("✓ Session heatmap generated")
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
        
        logger.info("👋 Nocturnal Eye stopped. Goodbye!")


def main():
    """Entry point"""
    parser = argparse.ArgumentParser(
        description='Nocturnal Eye - Gecko Activity Tracking System'
    )
    parser.add_argument(
        '--config',
        default='config.yaml',
        help='Path to configuration file'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug logging'
    )
    
    args = parser.parse_args()
    
    # Override config with debug flag
    if args.debug:
        # Load and modify config
        with open(args.config, 'r') as f:
            config = yaml.safe_load(f)
        config['logging']['level'] = 'DEBUG'
        
        # Write temporary debug config
        debug_config_path = 'config_debug.yaml'
        with open(debug_config_path, 'w') as f:
            yaml.dump(config, f)
        args.config = debug_config_path
    
    # Create and run application
    try:
        app = NocturnalEye(config_path=args.config)
        app.run()
    except Exception as e:
        print(f"Failed to start Nocturnal Eye: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
