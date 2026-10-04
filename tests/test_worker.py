import json
import uuid
import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy.orm import Session

from app.models.notification import Notification
from app.models.user import User
from app.models.enums import NotificationStatus, NotificationType, NotificationChannel
from worker.notification_worker import NotificationWorker
from tests.conftest import TestingSessionLocal

@pytest.fixture
def mock_worker():
    with patch('worker.notification_worker.get_rabbitmq_connection') as mock_conn:
        with patch('worker.notification_worker.SessionLocal', new=TestingSessionLocal):
            mock_channel = MagicMock()
            mock_conn.return_value.channel.return_value = mock_channel
            mock_conn.return_value.add_callback_threadsafe = lambda cb: cb()
            
            worker = NotificationWorker()
            yield worker

@pytest.fixture
def test_user(db: Session):
    user = User(
        email="worker_test@example.com",
        password_hash="hashed_password",
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

@pytest.fixture
def test_notification(db: Session, test_user: User):
    notification = Notification(
        user_id=test_user.id,
        type=NotificationType.WELCOME,
        channel=NotificationChannel.IN_APP,
        title="Test Notification",
        content="This is a test notification.",
        status=NotificationStatus.PENDING,
        retry_count=0
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return notification

def test_worker_processes_pending_notification(mock_worker, db: Session, test_notification: Notification):
    mock_ch = MagicMock()
    mock_method = MagicMock()
    mock_method.delivery_tag = 1
    
    body = json.dumps({"notification_id": str(test_notification.id)}).encode('utf-8')
    
    mock_worker._do_work(mock_ch, mock_method, None, body)
    
    mock_ch.basic_ack.assert_called_once_with(delivery_tag=1)
    db.refresh(test_notification)
    assert test_notification.status == NotificationStatus.SENT
    assert test_notification.sent_at is not None
    assert test_notification.retry_count == 0

def test_worker_does_not_process_sent_notification(mock_worker, db: Session, test_notification: Notification):
    test_notification.status = NotificationStatus.SENT
    db.commit()
    
    mock_ch = MagicMock()
    mock_method = MagicMock()
    mock_method.delivery_tag = 1
    
    body = json.dumps({"notification_id": str(test_notification.id)}).encode('utf-8')
    mock_worker._do_work(mock_ch, mock_method, None, body)
    
    mock_ch.basic_ack.assert_called_once_with(delivery_tag=1)
    db.refresh(test_notification)
    assert test_notification.status == NotificationStatus.SENT

def test_worker_does_not_process_failed_notification(mock_worker, db: Session, test_notification: Notification):
    test_notification.status = NotificationStatus.FAILED
    db.commit()
    
    mock_ch = MagicMock()
    mock_method = MagicMock()
    mock_method.delivery_tag = 1
    
    body = json.dumps({"notification_id": str(test_notification.id)}).encode('utf-8')
    mock_worker._do_work(mock_ch, mock_method, None, body)
    
    mock_ch.basic_ack.assert_called_once_with(delivery_tag=1)
    db.refresh(test_notification)
    assert test_notification.status == NotificationStatus.FAILED

def test_missing_notification_acks(mock_worker, db: Session):
    mock_ch = MagicMock()
    mock_method = MagicMock()
    mock_method.delivery_tag = 1
    
    body = json.dumps({"notification_id": str(uuid.uuid4())}).encode('utf-8')
    mock_worker._do_work(mock_ch, mock_method, None, body)
    
    mock_ch.basic_ack.assert_called_once_with(delivery_tag=1)

@patch('app.messaging.publisher.NotificationPublisher.publish_notification')
def test_first_delivery_failure_retries(mock_publish, mock_worker, db: Session, test_notification: Notification):
    test_notification.content = "Test notification [FAIL]"
    db.commit()
    
    mock_ch = MagicMock()
    mock_method = MagicMock()
    mock_method.delivery_tag = 1
    
    body = json.dumps({"notification_id": str(test_notification.id)}).encode('utf-8')
    mock_worker._do_work(mock_ch, mock_method, None, body)
    
    mock_ch.basic_ack.assert_called_once_with(delivery_tag=1)
    mock_publish.assert_called_once_with(test_notification.id)
    
    db.refresh(test_notification)
    assert test_notification.retry_count == 1
    assert test_notification.status == NotificationStatus.PENDING

@patch('app.messaging.publisher.NotificationPublisher.publish_notification')
def test_second_delivery_failure_retries(mock_publish, mock_worker, db: Session, test_notification: Notification):
    test_notification.content = "Test notification [FAIL]"
    test_notification.retry_count = 1
    db.commit()
    
    mock_ch = MagicMock()
    mock_method = MagicMock()
    mock_method.delivery_tag = 1
    
    body = json.dumps({"notification_id": str(test_notification.id)}).encode('utf-8')
    mock_worker._do_work(mock_ch, mock_method, None, body)
    
    mock_ch.basic_ack.assert_called_once_with(delivery_tag=1)
    mock_publish.assert_called_once_with(test_notification.id)
    
    db.refresh(test_notification)
    assert test_notification.retry_count == 2
    assert test_notification.status == NotificationStatus.PENDING

@patch('app.messaging.publisher.NotificationPublisher.publish_to_dlq')
def test_third_delivery_failure_dlq(mock_dlq, mock_worker, db: Session, test_notification: Notification):
    test_notification.content = "Test notification [FAIL]"
    test_notification.retry_count = 2
    # The max is 3, wait, if it's 2, incrementing makes it 3. If it's < 3 it retries, else DLQ.
    db.commit()
    
    mock_ch = MagicMock()
    mock_method = MagicMock()
    mock_method.delivery_tag = 1
    
    body = json.dumps({"notification_id": str(test_notification.id)}).encode('utf-8')
    mock_worker._do_work(mock_ch, mock_method, None, body)
    
    mock_ch.basic_ack.assert_called_once_with(delivery_tag=1)
    mock_dlq.assert_called_once_with(test_notification.id)
    
    db.refresh(test_notification)
    assert test_notification.retry_count == 3
    assert test_notification.status == NotificationStatus.FAILED

def test_successful_retry(mock_worker, db: Session, test_notification: Notification):
    # Simulate a notification that failed previously but now will succeed
    test_notification.retry_count = 1
    test_notification.content = "Normal notification"
    db.commit()
    
    mock_ch = MagicMock()
    mock_method = MagicMock()
    mock_method.delivery_tag = 1
    
    body = json.dumps({"notification_id": str(test_notification.id)}).encode('utf-8')
    mock_worker._do_work(mock_ch, mock_method, None, body)
    
    mock_ch.basic_ack.assert_called_once_with(delivery_tag=1)
    
    db.refresh(test_notification)
    assert test_notification.status == NotificationStatus.SENT
    assert test_notification.retry_count == 1  # unchanged because it succeeded

@patch('app.messaging.publisher.NotificationPublisher.publish_notification')
def test_retry_publish_fails_no_ack(mock_publish, mock_worker, db: Session, test_notification: Notification):
    test_notification.content = "Test notification [FAIL]"
    db.commit()
    
    mock_publish.side_effect = Exception("AMQP error")
    
    mock_ch = MagicMock()
    mock_method = MagicMock()
    mock_method.delivery_tag = 1
    
    body = json.dumps({"notification_id": str(test_notification.id)}).encode('utf-8')
    mock_worker._do_work(mock_ch, mock_method, None, body)
    
    mock_ch.basic_ack.assert_not_called()
    db.refresh(test_notification)
    assert test_notification.retry_count == 1
    assert test_notification.status == NotificationStatus.PENDING

@patch('app.messaging.publisher.NotificationPublisher.publish_to_dlq')
def test_dlq_publish_fails_no_ack(mock_dlq, mock_worker, db: Session, test_notification: Notification):
    test_notification.content = "Test notification [FAIL]"
    test_notification.retry_count = 2
    db.commit()
    
    mock_dlq.side_effect = Exception("AMQP error")
    
    mock_ch = MagicMock()
    mock_method = MagicMock()
    mock_method.delivery_tag = 1
    
    body = json.dumps({"notification_id": str(test_notification.id)}).encode('utf-8')
    mock_worker._do_work(mock_ch, mock_method, None, body)
    
    mock_ch.basic_ack.assert_not_called()
    db.refresh(test_notification)
    assert test_notification.retry_count == 3
    assert test_notification.status == NotificationStatus.FAILED
