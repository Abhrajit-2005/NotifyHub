import logging
from app.models.notification import Notification

logger = logging.getLogger(__name__)

class DeliveryService:
    @staticmethod
    def send_notification(notification: Notification) -> bool:
        """
        Simulates sending a notification based on its channel.
        """
        logger.info(f"[NotificationWorker] Sending {notification.channel.value} notification {notification.id} to user {notification.user_id}")
        
        # Simulate failure for testing purposes
        if notification.content and "[FAIL]" in notification.content:
            raise Exception("Simulated delivery failure")
            
        # Simulate some logic (e.g., formatting, calling external API)
        # Here we just assume success.
        
        logger.info(f"[NotificationWorker] Notification {notification.id} sent successfully")
        return True
