"""
Test suite for StreamConsumer retry logic
Tests retry_forever feature and its interaction with other configurations
"""

import pytest
import time
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock, PropertyMock
import numpy as np

from src.stream_consumer import StreamConsumer


class TestStreamConsumerRetryLogic:
    """Test cases for StreamConsumer retry behavior"""
    
    @pytest.fixture
    def config_retry_forever(self):
        """Configuration with retry_forever enabled"""
        return {
            'stream': {
                'url': 'http://test-server:8090/stream.m3u8',
                'timeout': 30,
                'max_retries': 3,
                'retry_delay': 0.1,  # Short delay for testing
                'retry_forever': True,
                'fallback_enabled': False,
                'fps_target': 2
            }
        }
    
    @pytest.fixture
    def config_max_retries(self):
        """Configuration with retry_forever disabled"""
        return {
            'stream': {
                'url': 'http://test-server:8090/stream.m3u8',
                'timeout': 30,
                'max_retries': 3,
                'retry_delay': 0.1,  # Short delay for testing
                'retry_forever': False,
                'fallback_enabled': False,
                'fps_target': 2
            }
        }
    
    @pytest.fixture
    def config_with_fallback(self):
        """Configuration with fallback enabled"""
        return {
            'stream': {
                'url': 'http://test-server:8090/stream.m3u8',
                'timeout': 30,
                'max_retries': 3,
                'retry_delay': 0.1,
                'retry_forever': False,
                'fallback_enabled': True,
                'fallback_path': '/tmp/test_fallback.mp4',
                'fps_target': 2
            }
        }
    
    def test_successful_connection_after_retries_with_retry_forever(self, config_retry_forever):
        """Test successful connection after multiple retries with retry_forever enabled"""
        consumer = StreamConsumer(config_retry_forever)
        
        # Create a mock capture that fails initially then succeeds
        mock_capture = MagicMock()
        
        # Track connection attempts
        attempt_count = [0]
        
        def mock_video_capture(url):
            attempt_count[0] += 1
            capture = MagicMock()
            
            # Fail first 2 attempts, succeed on 3rd
            if attempt_count[0] < 3:
                capture.read.return_value = (False, None)
            else:
                # Success on 3rd attempt
                frame = np.zeros((480, 640, 3), dtype=np.uint8)
                capture.read.return_value = (True, frame)
            
            return capture
        
        with patch('cv2.VideoCapture', side_effect=mock_video_capture):
            result = consumer.connect()
        
        assert result is True, "Should successfully connect after retries"
        assert attempt_count[0] == 3, "Should have made 3 connection attempts"
        assert consumer.capture is not None, "Capture should be set"
    
    def test_max_retries_reached_when_retry_forever_disabled(self, config_max_retries):
        """Test behavior when retry_forever is disabled and max_retries is reached"""
        consumer = StreamConsumer(config_max_retries)
        
        # Track connection attempts
        attempt_count = [0]
        
        def mock_video_capture(url):
            attempt_count[0] += 1
            capture = MagicMock()
            capture.read.return_value = (False, None)
            return capture
        
        with patch('cv2.VideoCapture', side_effect=mock_video_capture):
            result = consumer.connect()
        
        assert result is False, "Should fail after max_retries"
        expected_attempts = consumer.max_retries
        assert attempt_count[0] == expected_attempts, f"Should have made exactly {expected_attempts} attempts"
        assert consumer.capture is None, "Capture should be None after failure"
    
    def test_retry_forever_continues_beyond_max_retries(self, config_retry_forever):
        """Test that retry_forever continues retrying beyond max_retries limit"""
        consumer = StreamConsumer(config_retry_forever)
        
        # Track connection attempts
        attempt_count = [0]
        max_attempts = 10  # More than max_retries (3)
        
        def mock_video_capture(url):
            attempt_count[0] += 1
            capture = MagicMock()
            
            # Succeed after more attempts than max_retries
            if attempt_count[0] < max_attempts:
                capture.read.return_value = (False, None)
            else:
                frame = np.zeros((480, 640, 3), dtype=np.uint8)
                capture.read.return_value = (True, frame)
            
            return capture
        
        with patch('cv2.VideoCapture', side_effect=mock_video_capture):
            result = consumer.connect()
        
        assert result is True, "Should successfully connect with retry_forever"
        assert attempt_count[0] == max_attempts, f"Should have made {max_attempts} attempts"
    
    def test_keyboard_interrupt_during_retry_loop(self, config_retry_forever):
        """Test proper handling of KeyboardInterrupt during retry loop"""
        consumer = StreamConsumer(config_retry_forever)
        
        attempt_count = [0]
        
        def mock_video_capture(url):
            attempt_count[0] += 1
            if attempt_count[0] == 3:
                # Simulate KeyboardInterrupt on 3rd attempt
                raise KeyboardInterrupt("User interrupted")
            capture = MagicMock()
            capture.read.return_value = (False, None)
            return capture
        
        with patch('cv2.VideoCapture', side_effect=mock_video_capture):
            with pytest.raises(KeyboardInterrupt):
                consumer.connect()
        
        # Verify cleanup occurred
        assert consumer.capture is None, "Capture should be cleaned up after interrupt"
        assert attempt_count[0] == 3, "Should have interrupted on 3rd attempt"
    
    def test_retry_forever_with_fallback_disabled(self, config_retry_forever):
        """Test that retry_forever does not use fallback when fallback is disabled"""
        consumer = StreamConsumer(config_retry_forever)
        
        # Mock VideoCapture to always fail initially, then succeed
        attempt_count = [0]
        
        def mock_video_capture(url):
            attempt_count[0] += 1
            capture = MagicMock()
            
            # Succeed on 5th attempt
            if attempt_count[0] < 5:
                capture.read.return_value = (False, None)
            else:
                frame = np.zeros((480, 640, 3), dtype=np.uint8)
                capture.read.return_value = (True, frame)
            
            return capture
        
        with patch('cv2.VideoCapture', side_effect=mock_video_capture):
            result = consumer.connect()
        
        assert result is True, "Should successfully connect"
        # Verify fallback was not attempted
        assert attempt_count[0] == 5, "Should only try main stream, not fallback"
    
    def test_fallback_used_when_max_retries_reached(self, config_with_fallback):
        """Test interaction between max_retries and fallback configuration"""
        consumer = StreamConsumer(config_with_fallback)
        
        main_attempts = [0]
        fallback_attempted = [False]
        
        def mock_video_capture(url):
            if url == config_with_fallback['stream']['url']:
                main_attempts[0] += 1
                capture = MagicMock()
                capture.read.return_value = (False, None)
                return capture
            elif url == config_with_fallback['stream']['fallback_path']:
                fallback_attempted[0] = True
                capture = MagicMock()
                frame = np.zeros((480, 640, 3), dtype=np.uint8)
                capture.read.return_value = (True, frame)
                return capture
        
        with patch('cv2.VideoCapture', side_effect=mock_video_capture):
            with patch('pathlib.Path.exists', return_value=True):
                result = consumer.connect()
        
        assert result is True, "Should connect via fallback"
        assert main_attempts[0] == 3, "Should try main stream max_retries times"
        assert fallback_attempted[0] is True, "Should attempt fallback after max_retries"
    
    def test_retry_forever_ignores_fallback(self):
        """Test that retry_forever takes precedence over fallback configuration"""
        config = {
            'stream': {
                'url': 'http://test-server:8090/stream.m3u8',
                'timeout': 30,
                'max_retries': 3,
                'retry_delay': 0.1,
                'retry_forever': True,  # This should take precedence
                'fallback_enabled': True,
                'fallback_path': '/tmp/test_fallback.mp4',
                'fps_target': 2
            }
        }
        consumer = StreamConsumer(config)
        
        main_attempts = [0]
        
        def mock_video_capture(url):
            # Only main stream should be attempted
            main_attempts[0] += 1
            capture = MagicMock()
            
            # Succeed after several attempts (more than max_retries)
            if main_attempts[0] < 7:
                capture.read.return_value = (False, None)
            else:
                frame = np.zeros((480, 640, 3), dtype=np.uint8)
                capture.read.return_value = (True, frame)
            
            return capture
        
        with patch('cv2.VideoCapture', side_effect=mock_video_capture):
            result = consumer.connect()
        
        assert result is True, "Should successfully connect with retry_forever"
        assert main_attempts[0] == 7, "Should continue retrying main stream beyond max_retries"
    
    def test_retry_delay_respected(self, config_retry_forever):
        """Test that retry_delay is properly respected between attempts"""
        consumer = StreamConsumer(config_retry_forever)
        consumer.retry_delay = 0.2  # Set a measurable delay
        
        attempt_times = []
        
        def mock_video_capture(url):
            attempt_times.append(time.time())
            capture = MagicMock()
            
            # Succeed on 3rd attempt
            if len(attempt_times) < 3:
                capture.read.return_value = (False, None)
            else:
                frame = np.zeros((480, 640, 3), dtype=np.uint8)
                capture.read.return_value = (True, frame)
            
            return capture
        
        with patch('cv2.VideoCapture', side_effect=mock_video_capture):
            result = consumer.connect()
        
        assert result is True
        assert len(attempt_times) == 3
        
        # Check that delays were respected (with some tolerance)
        for i in range(1, len(attempt_times)):
            delay = attempt_times[i] - attempt_times[i-1]
            assert delay >= 0.2, f"Delay between attempts should be at least 0.2s, got {delay:.3f}s"
    
    def test_capture_cleanup_on_failed_attempts(self, config_max_retries):
        """Test that capture is properly cleaned up on each failed attempt"""
        consumer = StreamConsumer(config_max_retries)
        
        released_captures = []
        
        def mock_video_capture(url):
            capture = MagicMock()
            capture.read.return_value = (False, None)
            
            # Track release calls
            def track_release():
                released_captures.append(capture)
            capture.release = track_release
            
            return capture
        
        with patch('cv2.VideoCapture', side_effect=mock_video_capture):
            result = consumer.connect()
        
        assert result is False
        # Should have released capture for each failed attempt
        assert len(released_captures) == 3, "Should release capture on each failed attempt"
    
    def test_logging_shows_retry_count_correctly(self, config_retry_forever):
        """Test that logging correctly shows retry count (with or without total)"""
        consumer = StreamConsumer(config_retry_forever)
        
        log_messages = []
        
        # Capture log messages
        def mock_warning(msg):
            log_messages.append(msg)
        
        attempt_count = [0]
        
        def mock_video_capture(url):
            attempt_count[0] += 1
            capture = MagicMock()
            
            if attempt_count[0] < 4:
                capture.read.return_value = (False, None)
            else:
                frame = np.zeros((480, 640, 3), dtype=np.uint8)
                capture.read.return_value = (True, frame)
            
            return capture
        
        with patch('cv2.VideoCapture', side_effect=mock_video_capture):
            with patch('logging.Logger.warning', side_effect=mock_warning):
                result = consumer.connect()
        
        assert result is True
        # Should log warnings for each failed attempt
        assert len(log_messages) >= 3, "Should log warning for each retry"
        
        # Check that messages don't show max_retries when retry_forever is enabled
        for msg in log_messages:
            # When retry_forever is True, should not show "X/Y" format
            if "Connection attempt" in msg and "failed:" in msg:
                assert "/" not in msg, \
                    "Should not show 'X/Y' format when retry_forever is enabled"
    
    def test_logging_shows_max_retries_when_disabled(self, config_max_retries):
        """Test that logging shows max_retries when retry_forever is disabled"""
        consumer = StreamConsumer(config_max_retries)
        
        log_messages = []
        
        def mock_warning(msg):
            log_messages.append(msg)
        
        def mock_video_capture(url):
            capture = MagicMock()
            capture.read.return_value = (False, None)
            return capture
        
        with patch('cv2.VideoCapture', side_effect=mock_video_capture):
            with patch('logging.Logger.warning', side_effect=mock_warning):
                result = consumer.connect()
        
        assert result is False
        
        # Check that messages show max_retries when retry_forever is disabled
        retry_messages = [msg for msg in log_messages if "Connection attempt" in msg]
        assert len(retry_messages) > 0, "Should have retry messages"
        
        # Should show format like "Connection attempt 1/3 failed"
        for msg in retry_messages:
            if "Connection attempt" in msg and "failed:" in msg:
                assert "/3" in msg or "max_retries" in msg.lower(), \
                    "Should indicate max_retries when retry_forever is disabled"


class TestStreamConsumerConfiguration:
    """Test configuration handling for retry options"""
    
    def test_default_retry_forever_is_false(self):
        """Test that retry_forever defaults to False"""
        config = {
            'stream': {
                'url': 'http://test-server:8090/stream.m3u8',
                'timeout': 30,
                'max_retries': 5,
                'retry_delay': 10,
                'fps_target': 2
            }
        }
        consumer = StreamConsumer(config)
        
        assert consumer.retry_forever is False, "retry_forever should default to False"
    
    def test_explicit_retry_forever_false(self):
        """Test explicit retry_forever=False setting"""
        config = {
            'stream': {
                'url': 'http://test-server:8090/stream.m3u8',
                'timeout': 30,
                'max_retries': 5,
                'retry_delay': 10,
                'retry_forever': False,
                'fps_target': 2
            }
        }
        consumer = StreamConsumer(config)
        
        assert consumer.retry_forever is False
    
    def test_explicit_retry_forever_true(self):
        """Test explicit retry_forever=True setting"""
        config = {
            'stream': {
                'url': 'http://test-server:8090/stream.m3u8',
                'timeout': 30,
                'max_retries': 5,
                'retry_delay': 10,
                'retry_forever': True,
                'fps_target': 2
            }
        }
        consumer = StreamConsumer(config)
        
        assert consumer.retry_forever is True
    
    def test_all_retry_parameters_set_correctly(self):
        """Test that all retry-related parameters are set correctly"""
        config = {
            'stream': {
                'url': 'http://test-server:8090/stream.m3u8',
                'timeout': 45,
                'max_retries': 7,
                'retry_delay': 15,
                'retry_forever': True,
                'fps_target': 2
            }
        }
        consumer = StreamConsumer(config)
        
        assert consumer.timeout == 45
        assert consumer.max_retries == 7
        assert consumer.retry_delay == 15
        assert consumer.retry_forever is True


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
