"""
Pydantic schemas for Notification Service
"""
import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class NotificationResponse(BaseModel):
    """Schema for notification response"""
    id: uuid.UUID
    user_id: uuid.UUID
    incident_id: Optional[uuid.UUID] = None
    type: str
    title: str
    message: Optional[str] = None
    is_read: bool = False
    created_at: datetime

    class Config:
        from_attributes = True


class NotificationListResponse(BaseModel):
    """Schema for list of notifications"""
    data: List[NotificationResponse]
