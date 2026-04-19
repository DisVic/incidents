"""
API внутренних уведомлений (колокольчик) и настроек уведомлений.

Endpoint'ы:
- GET /notifications — список уведомлений пользователя
- POST /notifications — создать уведомление (из Celery-задач)
- POST /notifications/{id}/read — пометить как прочитанное
- POST /notifications/read-all — прочитать все уведомления
- GET /notifications/settings/{user_id} — настройки уведомлений
- PUT /notifications/settings/{user_id} — обновить настройки
"""
import uuid
from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from shared import get_db
from shared.models import Notification, NotificationSettings
from schemas import NotificationResponse

router = APIRouter()


@router.get("", response_model=List[NotificationResponse])
async def list_notifications(
    user_id: str,
    unread_only: bool = False,
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
):
    """
    Список уведомлений пользователя.
    
    Query params:
    - user_id: ID пользователя (обязательно)
    - unread_only: только непрочитанные (default: False)
    - limit: максимум уведомлений (default: 50)
    """
    query = select(Notification).where(Notification.user_id == uuid.UUID(user_id))
    
    if unread_only:
        query = query.where(Notification.is_read == False)
    
    query = query.order_by(Notification.created_at.desc()).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.post("")
async def create_notification(
    user_id: str,
    incident_id: str = None,
    type: str = "info",
    title: str = "",
    message: str = "",
    db: AsyncSession = Depends(get_db)
):
    """
    Создание уведомления.
    
    Вызывается из Celery-задач при событиях системы.
    """
    notification = Notification(
        user_id=uuid.UUID(user_id),
        incident_id=uuid.UUID(incident_id) if incident_id else None,
        type=type,
        title=title,
        message=message
    )
    db.add(notification)
    await db.commit()
    await db.refresh(notification)
    return notification


@router.post("/{notif_id}/read")
async def mark_read(notif_id: str, db: AsyncSession = Depends(get_db)):
    """Пометить уведомление как прочитанное."""
    result = await db.execute(select(Notification).where(Notification.id == notif_id))
    notif = result.scalar_one_or_none()
    if notif:
        notif.is_read = True
        await db.commit()
    return {"message": "Marked as read"}


@router.post("/read-all")
async def mark_all_read(user_id: str, db: AsyncSession = Depends(get_db)):
    """Пометить все уведомления пользователя как прочитанные."""
    result = await db.execute(
        select(Notification).where(
            Notification.user_id == uuid.UUID(user_id),
            Notification.is_read == False
        )
    )
    for notif in result.scalars().all():
        notif.is_read = True
    await db.commit()
    return {"message": "All marked as read"}


@router.get("/settings/{user_id}")
async def get_settings(user_id: str, db: AsyncSession = Depends(get_db)):
    """Получить настройки уведомлений пользователя."""
    result = await db.execute(
        select(NotificationSettings).where(NotificationSettings.user_id == uuid.UUID(user_id))
    )
    return result.scalar_one_or_none()


@router.put("/settings/{user_id}")
async def update_settings(user_id: str, settings: dict, db: AsyncSession = Depends(get_db)):
    """
    Обновить настройки уведомлений.
    
    settings: dict с типами уведомлений и их статусом (вкл/выкл).
    Пример: {"incident_created": {"internal": true, "email": false}}
    """
    result = await db.execute(
        select(NotificationSettings).where(NotificationSettings.user_id == uuid.UUID(user_id))
    )
    ns = result.scalar_one_or_none()
    
    if not ns:
        ns = NotificationSettings(user_id=uuid.UUID(user_id))
        db.add(ns)
    
    for key, value in settings.items():
        if hasattr(ns, key):
            setattr(ns, key, value)
    
    await db.commit()
    return ns
