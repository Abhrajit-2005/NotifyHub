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
    
    mock_worker._process_message(mock_ch, mock_method, None, body)
    
    # Assert message was acked
    mock_ch.basic_ack.assert_called_once_with(delivery_tag=1)
    
    # Assert notification status updated
    db.refresh(test_notification)
    assert test_notification.status == NotificationStatus.SENT
    assert test_notification.sent_at is not None

def test_worker_does_not_process_sent_notification(mock_worker, db: Session, test_notification: Notification):
    # Set it to SENT before processing
    test_notification.status = NotificationStatus.SENT
    db.commit()
    
    mock_ch = MagicMock()
    mock_method = MagicMock()
    mock_method.delivery_tag = 1
    
    body = json.dumps({"notification_id": str(test_notification.id)}).encode('utf-8')
    
    mock_worker._process_message(mock_ch, mock_method, None, body)
    
    # Should be acked
    mock_ch.basic_ack.assert_called_once_with(delivery_tag=1)
    
    # Should still be SENT, but sent_at shouldn't change
    db.refresh(test_notification)
    assert test_notification.status == NotificationStatus.SENT

@patch('worker.notification_worker.DeliveryService.send_notification')
def test_worker_failed_processing_nacks(mock_send, mock_worker, db: Session, test_notification: Notification):
    mock_send.return_value = False
    
    mock_ch = MagicMock()
    mock_method = MagicMock()
    mock_method.delivery_tag = 1
    
    body = json.dumps({"notification_id": str(test_notification.id)}).encode('utf-8')
    
    mock_worker._process_message(mock_ch, mock_method, None, body)
    
    # Assert message was nacked, not requeued (as configured for failed delivery)
    mock_ch.basic_nack.assert_called_once_with(delivery_tag=1, requeue=False)
    
    db.refresh(test_notification)
    assert test_notification.status == NotificationStatus.FAILED

def test_worker_exception_nacks_and_requeues(mock_worker, db: Session, test_notification: Notification):
    # Pass invalid JSON body to cause an exception
    mock_ch = MagicMock()
    mock_method = MagicMock()
    mock_method.delivery_tag = 1
    
    body = b"invalid json"
    
    mock_worker._process_message(mock_ch, mock_method, None, body)
    
    # Exception during parsing should cause NACK with requeue=True
    mock_ch.basic_nack.assert_called_once_with(delivery_tag=1, requeue=True)
