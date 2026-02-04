"""
Test suite for Detection Filter module
Tests time-based filtering logic for gecko activity detection windows
"""

import pytest
from datetime import datetime
from src.detection_filter import DetectionFilter


class TestDetectionFilter:
    """Test cases for DetectionFilter class"""
    
    @pytest.fixture
    def config_night_mode(self):
        """Configuration for night mode (10 PM - 6 AM)"""
        return {
            'detection_publishing': {
                'enabled': True,
                'active_hours': {
                    'start': '22:00',  # 10 PM
                    'end': '06:00'     # 6 AM
                }
            },
            'schedule': {'timezone': 'America/New_York'}
        }
    
    @pytest.fixture
    def config_disabled(self):
        """Configuration with filtering disabled"""
        return {
            'detection_publishing': {
                'enabled': False,
                'active_hours': {
                    'start': '22:00',
                    'end': '06:00'
                }
            },
            'schedule': {'timezone': 'America/New_York'}
        }
    
    def test_initialization(self, config_night_mode):
        """Test DetectionFilter initialization"""
        df = DetectionFilter(config_night_mode)
        assert df.enabled is True
        assert df.start_hour == 22
        assert df.start_minute == 0
        assert df.end_hour == 6
        assert df.end_minute == 0
    
    def test_parse_time_valid(self, config_night_mode):
        """Test time parsing with valid input"""
        df = DetectionFilter(config_night_mode)
        hour, minute = df._parse_time('14:30')
        assert hour == 14
        assert minute == 30
    
    def test_parse_time_midnight(self, config_night_mode):
        """Test time parsing for midnight"""
        df = DetectionFilter(config_night_mode)
        hour, minute = df._parse_time('00:00')
        assert hour == 0
        assert minute == 0
    
    def test_should_publish_when_disabled(self, config_disabled):
        """Test that publishing is always allowed when filtering is disabled"""
        df = DetectionFilter(config_disabled)
        # Test various times
        test_time_day = datetime(2026, 2, 3, 12, 0, 0)  # Noon
        test_time_night = datetime(2026, 2, 3, 23, 0, 0)  # 11 PM
        
        assert df.should_publish_detection(test_time_day) is True
        assert df.should_publish_detection(test_time_night) is True
    
    def test_should_publish_during_active_window_start(self, config_night_mode):
        """Test publishing is allowed at start of active window (10 PM)"""
        df = DetectionFilter(config_night_mode)
        test_time = datetime(2026, 2, 3, 22, 0, 0)  # 10 PM exactly
        assert df.should_publish_detection(test_time) is True
    
    def test_should_publish_during_active_window_middle(self, config_night_mode):
        """Test publishing is allowed in middle of night (2 AM)"""
        df = DetectionFilter(config_night_mode)
        test_time = datetime(2026, 2, 3, 2, 30, 0)  # 2:30 AM
        assert df.should_publish_detection(test_time) is True
    
    def test_should_publish_at_end_of_window(self, config_night_mode):
        """Test publishing just before end of active window (5:59 AM)"""
        df = DetectionFilter(config_night_mode)
        test_time = datetime(2026, 2, 3, 5, 59, 59)  # 5:59:59 AM
        assert df.should_publish_detection(test_time) is True
    
    def test_should_not_publish_after_window_ends(self, config_night_mode):
        """Test publishing is blocked after window ends (6:00 AM)"""
        df = DetectionFilter(config_night_mode)
        test_time = datetime(2026, 2, 3, 6, 0, 0)  # 6:00 AM exactly
        assert df.should_publish_detection(test_time) is False
    
    def test_should_not_publish_during_day(self, config_night_mode):
        """Test publishing is blocked during daytime (12 PM)"""
        df = DetectionFilter(config_night_mode)
        test_time = datetime(2026, 2, 3, 12, 0, 0)  # Noon
        assert df.should_publish_detection(test_time) is False
    
    def test_should_not_publish_just_before_window_starts(self, config_night_mode):
        """Test publishing is blocked just before window (9:59 PM)"""
        df = DetectionFilter(config_night_mode)
        test_time = datetime(2026, 2, 3, 21, 59, 59)  # 9:59:59 PM
        assert df.should_publish_detection(test_time) is False
    
    def test_wrapping_around_midnight(self, config_night_mode):
        """Test filtering correctly handles midnight boundary"""
        df = DetectionFilter(config_night_mode)
        
        # Before midnight (11 PM) - should publish
        before_midnight = datetime(2026, 2, 3, 23, 30, 0)
        assert df.should_publish_detection(before_midnight) is True
        
        # After midnight (1 AM) - should publish
        after_midnight = datetime(2026, 2, 4, 1, 0, 0)
        assert df.should_publish_detection(after_midnight) is True
    
    def test_get_active_window(self, config_night_mode):
        """Test retrieving active window configuration"""
        df = DetectionFilter(config_night_mode)
        window = df.get_active_window()
        
        assert window['enabled'] is True
        assert window['start'] == '22:00'
        assert window['end'] == '06:00'
        assert 'timezone' in window
    
    def test_get_next_active_time_during_active(self, config_night_mode):
        """Test next active time calculation when currently active"""
        df = DetectionFilter(config_night_mode)
        test_time = datetime(2026, 2, 3, 2, 0, 0)  # 2 AM (active)
        next_active = df.get_next_active_time(test_time)
        
        # When active, should return current time truncated to minutes
        expected = test_time.replace(second=0, microsecond=0)
        assert next_active == expected, f"Expected {expected}, got {next_active}"
    
    def test_get_next_active_time_during_inactive(self, config_night_mode):
        """Test next active time calculation when currently inactive"""
        df = DetectionFilter(config_night_mode)
        test_time = datetime(2026, 2, 3, 12, 0, 0)  # Noon (inactive)
        next_active = df.get_next_active_time(test_time)
        
        # Next active should be at 10 PM same day (before start time, so same day)
        expected = test_time.replace(hour=22, minute=0, second=0, microsecond=0)
        assert next_active == expected, f"Expected {expected}, got {next_active}"
        assert next_active.day == test_time.day, "Should return same day, not next day"
    
    def test_multiple_time_formats(self, config_night_mode):
        """Test various time formats are parsed correctly"""
        
        # Test without minutes
        config = {
            'detection_publishing': {
                'enabled': True,
                'active_hours': {'start': '22', 'end': '6'}
            },
            'schedule': {'timezone': 'America/New_York'}
        }
        df2 = DetectionFilter(config)
        assert df2.start_hour == 22
        assert df2.start_minute == 0
    
    def test_day_mode_window(self):
        """Test day mode window (active during day, not night)"""
        config = {
            'detection_publishing': {
                'enabled': True,
                'active_hours': {
                    'start': '06:00',  # 6 AM
                    'end': '22:00'     # 10 PM
                }
            },
            'schedule': {'timezone': 'America/New_York'}
        }
        df = DetectionFilter(config)
        
        # 12 PM - should be active
        noon = datetime(2026, 2, 3, 12, 0, 0)
        assert df.should_publish_detection(noon) is True
        
        # 2 AM - should be inactive
        early_morning = datetime(2026, 2, 3, 2, 0, 0)
        assert df.should_publish_detection(early_morning) is False


class TestDetectionFilterEdgeCases:
    """Edge case tests for DetectionFilter"""
    
    def test_start_equals_end_time(self):
        """Test behavior when start and end times are equal"""
        config = {
            'detection_publishing': {
                'enabled': True,
                'active_hours': {
                    'start': '22:00',
                    'end': '22:00'
                }
            },
            'schedule': {'timezone': 'America/New_York'}
        }
        df = DetectionFilter(config)
        
        # Should handle gracefully
        result = df.should_publish_detection(datetime(2026, 2, 3, 22, 0, 0))
        assert isinstance(result, bool)
    
    def test_invalid_time_string_fallback(self):
        """Test fallback when time string is invalid"""
        config = {
            'detection_publishing': {
                'enabled': True,
                'active_hours': {
                    'start': 'invalid',
                    'end': '06:00'
                }
            },
            'schedule': {'timezone': 'America/New_York'}
        }
        df = DetectionFilter(config)
        
        # Should fallback to 22:00
        assert df.start_hour == 22
        assert df.start_minute == 0
    
    def test_none_timestamp_uses_current_time(self):
        """Test that None timestamp uses current time"""
        config = {
            'detection_publishing': {
                'enabled': True,
                'active_hours': {
                    'start': '22:00',
                    'end': '06:00'
                }
            },
            'schedule': {'timezone': 'America/New_York'}
        }
        df = DetectionFilter(config)
        
        # Should not raise exception
        result = df.should_publish_detection(None)
        assert isinstance(result, bool)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
