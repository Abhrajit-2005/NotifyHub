import json
import logging
import uuid
import time
from datetime import datetime, timezone
import pika
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.core.config import settings
from app.models.notification import Notification
from app.models.enums import NotificationStatus
from app.services.delivery_service import DeliveryService
from app.messaging.rabbitmq import get_rabbitmq_connection

logger = logging.getLogger(__name__)

class NotificationWorker:
    def __init__(self):
        self._connection = None
        self._channel = None
        
        # Retry connection with exponential backoff on startup
        max_retries = 10
        for i in range(max_retries):
            try:
                self._connect_rabbitmq()
                break
            except Exception as e:
                logger.warning(f"Failed to connect to RabbitMQ (attempt {i+1}/{max_retries}): {e}")
                time.sleep(2 ** i)
        else:
             logger.error("Could not connect to RabbitMQ after multiple retries. Exiting.")
             raise Exception("Failed to connect to RabbitMQ.")

    def _connect_rabbitmq(self):
        self._connection = get_rabbitmq_connection()
        self._channel = self._connection.channel()
        self._channel.queue_declare(queue=settings.RABBITMQ_QUEUE, durable=True)
        self._channel.basic_qos(prefetch_count=1)
        self._channel.basic_consume(
            queue=settings.RABBITMQ_QUEUE,
            on_message_callback=self._process_message
        )
        logger.info("Successfully connected to RabbitMQ and declared queue.")

    def start(self):
        logger.info("[NotificationWorker] Starting to consume messages...")
        try:
            self._channel.start_consuming()
        except KeyboardInterrupt:
            logger.info("[NotificationWorker] Stopping consumer...")
            self._connection.close()
        except pika.exceptions.ConnectionClosedByBroker:
             logger.error("[NotificationWorker] Connection closed by broker.")
             
    def _process_message(self, ch, method, properties, body):
        db: Session = SessionLocal()
        try:
            logger.info(f"[NotificationWorker] Message received: {body}")
            data = json.loads(body)
            notification_id_str = data.get("notification_id")
            
            if not notification_id_str:
                logger.error("No notification_id found in message body.")
                ch.basic_ack(delivery_tag=method.delivery_tag)
                return
                
            try:
                notification_id = uuid.UUID(notification_id_str)
            except ValueError:
                logger.error(f"Invalid notification_id format: {notification_id_str}")
                ch.basic_ack(delivery_tag=method.delivery_tag)
                return

            notification = db.query(Notification).filter(Notification.id == notification_id).first()
            if not notification:
                logger.warning(f"Notification {notification_id} not found in database.")
                ch.basic_ack(delivery_tag=method.delivery_tag)
                return

            if notification.status == NotificationStatus.SENT:
                logger.info(f"Notification {notification_id} is already SENT. Ignoring.")
                ch.basic_ack(delivery_tag=method.delivery_tag)
                return

            if notification.status == NotificationStatus.PENDING:
                # Use conditional update for concurrency safety
                updated = db.query(Notification).filter(
                    Notification.id == notification_id,
                    Notification.status == NotificationStatus.PENDING
                ).update({"status": NotificationStatus.PROCESSING})
                
                if not updated:
                    logger.warning(f"Failed to transition notification {notification_id} to PROCESSING. Another worker might have processed it.")
                    db.rollback()
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                    return
                
                db.commit()
                db.refresh(notification)

            logger.info(f"[NotificationWorker] Notification processing started for {notification_id}")
            
            # Simulate delivery
            success = DeliveryService.send_notification(notification)
            
            if success:
                notification.status = NotificationStatus.SENT
                notification.sent_at = datetime.now(timezone.utc)
                db.commit()
                logger.info(f"[NotificationWorker] Notification processing succeeded for {notification_id}")
                ch.basic_ack(delivery_tag=method.delivery_tag)
                logger.info(f"[NotificationWorker] Message acknowledged for {notification_id}")
            else:
                notification.status = NotificationStatus.FAILED
                db.commit()
                logger.error(f"[NotificationWorker] Notification processing failed for {notification_id}")
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
                
        except Exception as e:
            logger.error(f"[NotificationWorker] Unexpected error processing message: {e}")
            db.rollback()
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
        finally:
            db.close()
