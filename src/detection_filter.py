"""
Detection Filter - Controls when detections are published based on time windows
Helps reduce false positives from daytime interference by filtering publications
"""

import logging
from datetime import datetime
from typing import Dict, Tuple, Optional

logger = logging.getLogger(__name__)


class DetectionFilter:
    """Manages detection publishing based on configurable time windows"""
    
    def __init__(self, config: dict):
        """
        Initialize detection filter
        
        Args:
            config: Configuration dictionary containing detection_publishing settings
        """
        self.config = config
        pub_config = config.get('detection_publishing', {})
        self.enabled = pub_config.get('enabled', True)
        
        # Parse active hours
        active_hours = pub_config.get('active_hours', {})
        self.start_time_str = active_hours.get('start', '22:00')  # 10 PM default
        self.end_time_str = active_hours.get('end', '06:00')      # 6 AM default
        
        # Parse time strings (HH:MM format)
        self.start_hour, self.start_minute = self._parse_time(self.start_time_str)
        self.end_hour, self.end_minute = self._parse_time(self.end_time_str)
        
        self.timezone = config.get('schedule', {}).get('timezone', 'America/New_York')
        
        logger.info(
            f"DetectionFilter initialized - enabled={self.enabled}, "
            f"active_hours={self.start_time_str}-{self.end_time_str}"
        )
    
    def _parse_time(self, time_str: str) -> Tuple[int, int]:
        """
        Parse time string in HH:MM format
        
        Args:
            time_str: Time string like "22:00" or "06:00"
            
        Returns:
            Tuple of (hour, minute)
        """
        try:
            parts = time_str.split(':')
            hour = int(parts[0])
            minute = int(parts[1]) if len(parts) > 1 else 0
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                raise ValueError(
                    f"Time components out of range in '{time_str}': hour={hour}, minute={minute}"
                )
            return hour, minute
        except (ValueError, IndexError) as e:
            logger.warning(f"Failed to parse time '{time_str}': {e}. Using default 22:00")
            return 22, 0
    
    def should_publish_detection(self, timestamp: Optional[datetime] = None) -> bool:
        """
        Determine if a detection should be published based on time windows
        
        This helps reduce noise from daytime interference like:
        - Shadows and reflections
        - Family members walking past the tank
        - Feeding activities
        - Light changes and reflections
        
        Args:
            timestamp: Datetime to check (defaults to current time)
            
        Returns:
            True if detection should be published, False otherwise
        """
        if not self.enabled:
            return True
        
        if timestamp is None:
            timestamp = datetime.now()
        
        current_hour = timestamp.hour
        current_minute = timestamp.minute
        
        # Convert times to minutes for easier comparison
        current_minutes = current_hour * 60 + current_minute
        start_minutes = self.start_hour * 60 + self.start_minute
        end_minutes = self.end_hour * 60 + self.end_minute
        
        # If start_time > end_time, it wraps around midnight
        # Example: 22:00 (1320 mins) to 06:00 (360 mins)
        if start_minutes > end_minutes:
            # Active during night (wraps around midnight)
            is_active = current_minutes >= start_minutes or current_minutes < end_minutes
        else:
            # Active during day
            is_active = current_minutes >= start_minutes and current_minutes < end_minutes
        
        if not is_active:
            logger.debug(
                f"Detection at {timestamp.strftime('%H:%M:%S')} outside active hours "
                f"({self.start_time_str}-{self.end_time_str}). Filtering out."
            )
        
        return is_active
    
    def get_active_window(self) -> Dict[str, str]:
        """
        Get the current active detection window configuration
        
        Returns:
            Dictionary with start and end times
        """
        return {
            'enabled': self.enabled,
            'start': self.start_time_str,
            'end': self.end_time_str,
            'timezone': self.timezone
        }
    
    def get_next_active_time(self, timestamp: Optional[datetime] = None) -> datetime:
        """
        Calculate the next time when detections will be published
        Useful for UI notifications about when gecko monitoring becomes active
        
        Args:
            timestamp: Datetime to check from (defaults to current time)
            
        Returns:
            Datetime of next active window start
        """
        if not self.enabled:
            return timestamp or datetime.now()
        
        if timestamp is None:
            timestamp = datetime.now()
        
        # Calculate next active period
        current_datetime = timestamp.replace(second=0, microsecond=0)
        start_time = current_datetime.replace(hour=self.start_hour, minute=self.start_minute)
        
        current_minutes = current_datetime.hour * 60 + current_datetime.minute
        start_minutes = self.start_hour * 60 + self.start_minute
        end_minutes = self.end_hour * 60 + self.end_minute
        
        if start_minutes > end_minutes:
            # Night mode (wraps around midnight)
            if current_minutes >= start_minutes or current_minutes < end_minutes:
                # Currently active (after start or before end)
                return current_datetime
            else:
                # Between end and start (inactive daytime), next active is tonight at start_time
                return current_datetime.replace(hour=self.start_hour, minute=self.start_minute)
        else:
            # Day mode
            if current_minutes >= start_minutes and current_minutes < end_minutes:
                # Already active
                return current_datetime
            else:
                # Next active window
                next_active = current_datetime.replace(
                    hour=self.start_hour,
                    minute=self.start_minute
                )
                if next_active <= current_datetime:
                    # Add 1 day
                    next_active = next_active.replace(day=next_active.day + 1)
                return next_active
