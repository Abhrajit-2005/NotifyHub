import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field
from app.models.enums import NotificationType, NotificationChannel, NotificationStatus

class NotificationCreate(BaseModel):
    type: NotificationType
    channel: NotificationChannel
    title: str = Field(..., min_length=1, max_length=255)
    content: str = Field(..., min_length=1)
    idempotency_key: Optional[str] = Field(None, max_length=255)

class NotificationResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    type: NotificationType
    channel: NotificationChannel
    title: str
    content: str
    status: NotificationStatus
    retry_count: int
    idempotency_key: Optional[str] = None
    is_read: bool
    created_at: datetime
    sent_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class NotificationPaginatedResponse(BaseModel):
    notifications: List[NotificationResponse]
    page: int
    page_size: int
    total: int
