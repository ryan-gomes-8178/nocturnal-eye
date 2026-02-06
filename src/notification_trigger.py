"""
Nocturnal Eye Notification Trigger
Sends notifications to TerrariumPI when gecko motion is detected
"""

import requests
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class NotificationTrigger:
    """Triggers TerrariumPI notifications when gecko activity is detected"""
    
    def __init__(self, terrariumpi_url="http://localhost:8090", rate_limit_seconds=300):
        """
        Initialize notification trigger
        
        Args:
            terrariumpi_url: Base URL of TerrariumPI service
            rate_limit_seconds: Minimum seconds between notifications (prevent spam)
        """
        self.terrariumpi_url = terrariumpi_url
        self.rate_limit_seconds = rate_limit_seconds
        self.last_notification_time = None
        self.gecko_detection_message_id = "d93a467a37dad33b55b2c816e48554cf"
    
    def should_notify(self):
        """Check if enough time has passed since last notification"""
        if self.last_notification_time is None:
            return True
        
        time_since_last = datetime.now() - self.last_notification_time
        return time_since_last.total_seconds() >= self.rate_limit_seconds
    
    def send_gecko_detection_notification(self, confidence=None, zone=None):
        """
        Send a notification to TerrariumPI about gecko detection
        
        Args:
            confidence: Detection confidence level (0.0-1.0)
            zone: Zone name where detection occurred
        
        Returns:
            bool: True if notification sent successfully
        """
        if not self.should_notify():
            logger.debug("Rate limit not met, skipping notification")
            return False
        
        try:
            # Build message with detection details
            message = "Nocturnal Eye motion detection captured activity! 🦎"
            
            if zone:
                message += f"\nZone: {zone}"
            
            if confidence:
                message += f"\nConfidence: {confidence:.1%}"
            
            # Use TerrariumPI's webhook endpoint to trigger notification
            # This bypasses the need for a custom endpoint and uses TerrariumPI's built-in notification system
            notification_payload = {
                "title": "I SAW MARTY!!!!",
                "message": message,
                "type": "gecko_detection"
            }
            
            # Try the direct webhook approach first
            response = requests.post(
                f"{self.terrariumpi_url}/api/notifications/webhook",
                json=notification_payload,
                timeout=5
            )
            
            if response.status_code in [200, 201, 204]:
                logger.info(f"✅ Gecko detection notification sent! {zone or 'General area'}")
                self.last_notification_time = datetime.now()
                return True
            elif response.status_code == 404:
                # Fallback: Try using the message-based endpoint directly
                # This sends to all configured notification services
                logger.debug("Webhook endpoint not found, trying message-based approach...")
                response = requests.post(
                    f"{self.terrariumpi_url}/api/notification/messages/{self.gecko_detection_message_id}",
                    json={"title": notification_payload["title"], "message": notification_payload["message"]},
                    timeout=5
                )
                if response.status_code in [200, 201, 204]:
                    logger.info(f"✅ Gecko detection notification sent! {zone or 'General area'}")
                    self.last_notification_time = datetime.now()
                    return True
                else:
                    logger.warning(f"Notification endpoint returned {response.status_code}: {response.text}")
                    return False
            else:
                logger.warning(f"Notification endpoint returned {response.status_code}: {response.text}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.warning(f"Failed to send notification: {e}")
            return False
        except Exception as e:
            logger.error(f"Error sending notification: {e}")
            return False


# Global instance
_notification_trigger = None


def get_notification_trigger():
    """Get or create the global notification trigger instance"""
    global _notification_trigger
    if _notification_trigger is None:
        _notification_trigger = NotificationTrigger()
    return _notification_trigger


def notify_gecko_detection(confidence=None, zone=None):
    """
    Convenience function to send gecko detection notification
    
    Args:
        confidence: Detection confidence level
        zone: Zone name where detection occurred
    
    Returns:
        bool: True if notification sent
    """
    return get_notification_trigger().send_gecko_detection_notification(confidence, zone)
