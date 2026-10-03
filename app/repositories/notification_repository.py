import uuid
from typing import Optional, List, Tuple
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.models.notification import Notification

class NotificationRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, notification: Notification) -> Notification:
        self.db.add(notification)
        self.db.commit()
        self.db.refresh(notification)
        return notification

    def get_by_id(self, notification_id: uuid.UUID, user_id: Optional[uuid.UUID] = None) -> Optional[Notification]:
        statement = select(Notification).where(Notification.id == notification_id)
        if user_id is not None:
            statement = statement.where(Notification.user_id == user_id)
        return self.db.scalar(statement)

    def get_by_idempotency_key(self, user_id: uuid.UUID, idempotency_key: str) -> Optional[Notification]:
        statement = select(Notification).where(
            Notification.user_id == user_id,
            Notification.idempotency_key == idempotency_key
        )
        return self.db.scalar(statement)

    def get_multi_by_user(
        self, user_id: uuid.UUID, page: int = 1, page_size: int = 20
    ) -> Tuple[List[Notification], int]:
        count_stmt = select(func.count()).select_from(Notification).where(Notification.user_id == user_id)
        total = self.db.scalar(count_stmt) or 0

        offset = (page - 1) * page_size
        stmt = (
            select(Notification)
            .where(Notification.user_id == user_id)
            .order_by(Notification.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        notifications = list(self.db.scalars(stmt).all())
        return notifications, total

    def save(self, notification: Notification) -> Notification:
        self.db.add(notification)
        self.db.commit()
        self.db.refresh(notification)
        return notification
