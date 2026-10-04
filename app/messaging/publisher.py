import json
import logging
import uuid
import pika
from pika.exceptions import AMQPError
from app.core.config import settings
from app.messaging.rabbitmq import get_rabbitmq_connection

logger = logging.getLogger(__name__)

class NotificationPublisher:
    def __init__(self):
        self._connection = None
        self._channel = None
        self._connect()

    def _connect(self):
        try:
            self._connection = get_rabbitmq_connection()
            self._channel = self._connection.channel()
            # Declare the durable queues
            self._channel.queue_declare(queue=settings.RABBITMQ_QUEUE, durable=True)
            self._channel.queue_declare(queue=settings.RABBITMQ_DLQ, durable=True)
        except Exception as e:
            logger.error(f"Error connecting to RabbitMQ in publisher: {e}")
            self._connection = None
            self._channel = None

    def publish_notification(self, notification_id: uuid.UUID) -> bool:
        """Publishes the notification ID to RabbitMQ."""
        return self._publish(settings.RABBITMQ_QUEUE, notification_id)

    def publish_to_dlq(self, notification_id: uuid.UUID) -> bool:
        """Publishes the notification ID to the Dead Letter Queue."""
        return self._publish(settings.RABBITMQ_DLQ, notification_id)

    def _publish(self, queue_name: str, notification_id: uuid.UUID) -> bool:
        if not self._connection or self._connection.is_closed or not self._channel or self._channel.is_closed:
            logger.warning("RabbitMQ connection closed, attempting to reconnect...")
            self._connect()
            
        if not self._channel:
             logger.error("Failed to publish message: No RabbitMQ channel available.")
             return False

        message = {
            "notification_id": str(notification_id)
        }
        
        try:
            self._channel.basic_publish(
                exchange='',
                routing_key=queue_name,
                body=json.dumps(message),
                properties=pika.BasicProperties(
                    delivery_mode=pika.DeliveryMode.Persistent, # Make message persistent
                )
            )
            logger.info(f"Published notification_id {notification_id} to queue {queue_name}")
            return True
        except AMQPError as e:
            logger.error(f"AMQP Error publishing message to {queue_name}: {e}")
            self._connection = None # Force reconnect next time
            raise
        except Exception as e:
            logger.error(f"Unexpected error publishing message to {queue_name}: {e}")
            raise

    def close(self):
        if self._connection and not self._connection.is_closed:
            self._connection.close()
            
publisher = NotificationPublisher()
