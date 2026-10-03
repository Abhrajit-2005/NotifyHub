import uuid
from typing import List, Tuple
from fastapi import HTTPException, status
from app.models.notification import Notification
from app.models.enums import NotificationStatus, NotificationChannel
from app.schemas.notification import NotificationCreate, NotificationPaginatedResponse, NotificationResponse
from app.repositories.notification_repository import NotificationRepository
from app.messaging import publisher

class NotificationService:
    def __init__(self, notification_repo: NotificationRepository):
        self.notification_repo = notification_repo

    def create_notification(
        self, user_id: uuid.UUID, notification_in: NotificationCreate
    ) -> Notification:
        if notification_in.idempotency_key:
            existing = self.notification_repo.get_by_idempotency_key(
                user_id, notification_in.idempotency_key
            )
            if existing:
                return existing

        notification = Notification(
            user_id=user_id,
            type=notification_in.type,
            channel=notification_in.channel,
            title=notification_in.title,
            content=notification_in.content,
            status=NotificationStatus.PENDING,
            retry_count=0,
            idempotency_key=notification_in.idempotency_key,
            is_read=False,
        )
        saved_notification = self.notification_repo.create(notification)
        
        # Publish notification ID to RabbitMQ
        publisher.publish_notification(saved_notification.id)
        
        return saved_notification


    def get_user_notifications(
        self, user_id: uuid.UUID, page: int = 1, page_size: int = 20
    ) -> NotificationPaginatedResponse:
        notifications, total = self.notification_repo.get_multi_by_user(
            user_id, page=page, page_size=page_size
        )
        notification_responses = [
            NotificationResponse.model_validate(n) for n in notifications
        ]
        return NotificationPaginatedResponse(
            notifications=notification_responses,
            page=page,
            page_size=page_size,
            total=total,
        )

    def get_notification_by_id(
        self, user_id: uuid.UUID, notification_id: uuid.UUID
    ) -> Notification:
        notification = self.notification_repo.get_by_id(notification_id, user_id=user_id)
        if not notification:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification not found"
            )
        return notification

    def mark_notification_as_read(
        self, user_id: uuid.UUID, notification_id: uuid.UUID
    ) -> Notification:
        notification = self.notification_repo.get_by_id(notification_id, user_id=user_id)
        if not notification:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification not found"
            )

        if notification.channel != NotificationChannel.IN_APP:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only IN_APP notifications can be marked as read"
            )

        notification.is_read = True
        return self.notification_repo.save(notification)
