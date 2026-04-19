"""
Pydantic-схемы для Notification Service.

Классы:
- NotificationResponse: данные уведомления
- NotificationListResponse: список уведомлений
"""
import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class NotificationResponse(BaseModel):
    """Данные уведомления для API-ответа."""
    id: uuid.UUID
    user_id: uuid.UUID
    incident_id: Optional[uuid.UUID] = None
    type: str  # notification, escalation, comment, etc.
    title: str
    message: Optional[str] = None
    is_read: bool = False
    created_at: datetime

    class Config:
        from_attributes = True


class NotificationListResponse(BaseModel):
    """Ответ со списком уведомлений."""
    data: List[NotificationResponse]
