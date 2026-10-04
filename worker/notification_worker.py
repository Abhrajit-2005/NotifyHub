import json
import logging
import uuid
import time
import threading
import functools
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
        thread = threading.Thread(target=self._do_work, args=(ch, method, properties, body))
        thread.start()

    def _ack_message(self, ch, delivery_tag):
        if ch.is_open:
            ch.basic_ack(delivery_tag=delivery_tag)

    def _do_work(self, ch, method, properties, body):
        db: Session = SessionLocal()
        try:
            logger.info(f"[NotificationWorker] Message received: {body}")
            data = json.loads(body)
            notification_id_str = data.get("notification_id")
            
            if not notification_id_str:
                logger.error("No notification_id found in message body.")
                self._connection.add_callback_threadsafe(functools.partial(self._ack_message, ch, method.delivery_tag))
                return
                
            try:
                notification_id = uuid.UUID(notification_id_str)
            except ValueError:
                logger.error(f"Invalid notification_id format: {notification_id_str}")
                self._connection.add_callback_threadsafe(functools.partial(self._ack_message, ch, method.delivery_tag))
                return

            notification = db.query(Notification).filter(Notification.id == notification_id).first()
            if not notification:
                logger.warning(f"Notification {notification_id} not found in database.")
                self._connection.add_callback_threadsafe(functools.partial(self._ack_message, ch, method.delivery_tag))
                return

            if notification.status == NotificationStatus.SENT:
                logger.info(f"Notification {notification_id} is already SENT. Ignoring.")
                self._connection.add_callback_threadsafe(functools.partial(self._ack_message, ch, method.delivery_tag))
                return

            if notification.status == NotificationStatus.FAILED:
                logger.info(f"Notification {notification_id} is already FAILED. Ignoring.")
                self._connection.add_callback_threadsafe(functools.partial(self._ack_message, ch, method.delivery_tag))
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
                    self._connection.add_callback_threadsafe(functools.partial(self._ack_message, ch, method.delivery_tag))
                    return
                
                db.commit()
                db.refresh(notification)

            logger.info(f"[NotificationWorker] Notification processing started for {notification_id}")
            
            try:
                # Simulate delivery
                success = DeliveryService.send_notification(notification)
                if success:
                    notification.status = NotificationStatus.SENT
                    notification.sent_at = datetime.now(timezone.utc)
                    db.commit()
                    logger.info(f"[NotificationWorker] Notification processing succeeded for {notification_id}")
                    self._connection.add_callback_threadsafe(functools.partial(self._ack_message, ch, method.delivery_tag))
                    logger.info(f"[NotificationWorker] Message acknowledged for {notification_id}")
                else:
                    raise Exception("Delivery service returned false")
            except Exception as delivery_error:
                db.rollback()
                logger.error(f"[NotificationWorker] Delivery failed for {notification_id}: {delivery_error}")
                
                # Atomically increment retry count
                # Using conditional update
                updated_retry = db.query(Notification).filter(
                    Notification.id == notification_id
                ).update({Notification.retry_count: Notification.retry_count + 1})
                db.commit()
                db.refresh(notification)
                
                logger.info(f"[NotificationWorker] Delivery failed for {notification_id}, retry_count={notification.retry_count}")
                
                try:
                    if notification.retry_count < settings.MAX_NOTIFICATION_RETRIES:
                        notification.status = NotificationStatus.PENDING
                        db.commit()
                        from app.messaging.publisher import publisher
                        publisher.publish_notification(notification_id)
                        logger.info(f"[NotificationWorker] Re-published {notification_id} for retry")
                    else:
                        logger.warning(f"[NotificationWorker] Retry limit reached for {notification_id}")
                        notification.status = NotificationStatus.FAILED
                        db.commit()
                        from app.messaging.publisher import publisher
                        publisher.publish_to_dlq(notification_id)
                        logger.info(f"[NotificationWorker] Notification {notification_id} moved to DLQ")
                        
                    self._connection.add_callback_threadsafe(functools.partial(self._ack_message, ch, method.delivery_tag))
                except Exception as publish_error:
                    logger.error(f"[NotificationWorker] Failed to publish retry/DLQ message for {notification_id}: {publish_error}")
                    # DO NOT ACK. Return so that it remains unacknowledged and can be redelivered.
                    return
                
        except Exception as e:
            logger.error(f"[NotificationWorker] Unexpected error processing message: {e}")
            db.rollback()
            # We acknowledge the message instead of requeuing to prevent infinite loops on malformed messages.
            # Real-world applications might want to DLQ it directly.
            self._connection.add_callback_threadsafe(functools.partial(self._ack_message, ch, method.delivery_tag))
        finally:
            db.close()
