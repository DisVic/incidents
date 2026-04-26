"""
Celery-задачи: мониторинг SLA, эскалация, отправка уведомлений.

Задачи запускаются каждые 5 минут через Celery Beat:
- check_sla_overdue — проверка просрочек SLA
- check_escalation — проверка эскалации (80% SLA)

Уведомления по событиям:
- notify_incident_created — новый инцидент
- notify_incident_assigned — назначение исполнителя
- notify_status_changed — смена статуса
- notify_new_comment — новый комментарий
- notify_incident_resolved/closed — решение/закрытие
- notify_priority_changed — изменение приоритета
"""
import logging
from datetime import datetime
from celery import shared_task
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
from uuid import UUID

from shared.celery_app import celery_app
from shared.config import settings
from shared.database import async_session
from shared.models import (
    Incident, Status, User, Role, Notification,
    EscalationRule, IncidentHistory, NotificationSettings
)
from shared.utils import get_sla_percentage

logger = logging.getLogger(__name__)


async def get_user_notification_settings(db, user_id: UUID) -> dict:
    """Получает настройки уведомлений пользователя (или дефолтные)."""
    result = await db.execute(
        select(NotificationSettings).where(NotificationSettings.user_id == user_id)
    )
    ns = result.scalar_one_or_none()
    
    if not ns:
        # Возвращаем настройки по умолчанию (все уведомления включены)
        return {
            "incident_created": {"internal": True, "email": True},
            "assigned_executor": {"internal": True, "email": True},
            "new_comment": {"internal": True, "email": True},
            "status_changed": {"internal": True, "email": True},
            "incident_resolved": {"internal": True, "email": True},
            "overdue": {"internal": True, "email": True},
            "escalation": {"internal": True, "email": True},
            "priority_changed": {"internal": True, "email": True},
        }
    
    return {
        "incident_created": ns.incident_created or {"internal": True, "email": True},
        "assigned_executor": ns.assigned_executor or {"internal": True, "email": True},
        "new_comment": ns.new_comment or {"internal": True, "email": True},
        "status_changed": ns.status_changed or {"internal": True, "email": True},
        "incident_resolved": ns.incident_resolved or {"internal": True, "email": True},
        "overdue": ns.overdue or {"internal": True, "email": True},
        "escalation": ns.escalation or {"internal": True, "email": True},
        "priority_changed": ns.priority_changed or {"internal": True, "email": True},
    }


async def send_internal_notification(db, user_id: UUID, incident_id: UUID, 
                                      type: str, title: str, message: str):
    """Создаёт внутреннее уведомление (колокольчик) в БД."""
    notification = Notification(
        user_id=user_id,
        incident_id=incident_id,
        type=type,
        title=title,
        message=message
    )
    db.add(notification)


async def send_email_notification(user: User, incident: Incident, 
                                   email_type: str, extra: dict = None):
    """
    Отправляет email через notification-service (HTML-шаблоны).
    
    Args:
        user: Получатель
        incident: Данные инцидента для шаблона
        email_type: Тип письма (incident_created, sla_overdue, etc.)
        extra: Дополнительные данные для шаблона
    """
    import httpx
    
    if not user.email:
        return
    
    # Формируем данные инцидента для шаблона
    incident_data = {
        "id": str(incident.id),
        "title": incident.title,
        "description": incident.description,
        "priority_name": getattr(incident.priority, "name", None) if hasattr(incident, 'priority') else None,
        "category_name": getattr(incident.category, "name", None) if hasattr(incident, 'category') else None,
        "department_name": getattr(incident.department, "name", None) if hasattr(incident, 'department') else None,
        "initiator_name": getattr(incident.initiator, "full_name", None) if hasattr(incident, 'initiator') else None,
        "executor_name": getattr(incident.executor, "full_name", None) if hasattr(incident, 'executor') else None,
        "sla_deadline": incident.sla_deadline.isoformat() if incident.sla_deadline else None,
        "created_at": incident.created_at.isoformat() if incident.created_at else None,
    }
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"http://notification-service:8004/email/send-templated",
                json={
                    "to": user.email,
                    "email_type": email_type,
                    "incident": incident_data,
                    "extra": extra or {},
                    "base_url": getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')
                }
            )
            if response.status_code == 200:
                logger.info(f"Email sent to {user.email}")
            else:
                logger.error(f"Failed to send email: {response.text}")
    except Exception as e:
        logger.error(f"Email notification error: {e}")


async def send_notification_with_settings(db, user: User, incident: Incident,
                                           event_type: str, email_type: str,
                                           title: str, message: str,
                                           extra: dict = None):
    """
    Отправляет уведомление с учётом настроек пользователя (internal/email).
    
    Args:
        event_type: Тип события для проверки настроек (incident_created, etc.)
        email_type: Тип email-шаблона
    """
    user_settings = await get_user_notification_settings(db, user.id)
    event_settings = user_settings.get(event_type, {"internal": True, "email": True})
    
    # Внутреннее уведомление
    if event_settings.get("internal", True):
        await send_internal_notification(db, user.id, incident.id, event_type, title, message)
    
    # Email
    if event_settings.get("email", True):
        await send_email_notification(user, incident, email_type, extra)


@celery_app.task(name="shared.tasks.check_sla_overdue")
def check_sla_overdue():
    """
    Проверка активных инцидентов на просрочку SLA (каждые 5 мин).
    
    Устанавливает overdue=True, отправляет уведомления Manager/Admin.
    """
    import asyncio
    return asyncio.run(_check_sla_overdue_async())


async def _check_sla_overdue_async():
    async with async_session() as db:
        # Получаем активные статусы (Новый, Назначен, В работе)
        active_status_names = ["Новый", "Назначен", "В работе"]
        status_result = await db.execute(
            select(Status).where(Status.name.in_(active_status_names))
        )
        active_statuses = status_result.scalars().all()
        active_status_ids = [s.id for s in active_statuses]
        
        # Находим инциденты с просрочкой, но ещё не помеченные
        now = datetime.utcnow()
        result = await db.execute(
            select(Incident)
            .options(
                selectinload(Incident.status),
                selectinload(Incident.initiator),
                selectinload(Incident.executor),
                selectinload(Incident.priority),
                selectinload(Incident.category),
                selectinload(Incident.department)
            )
            .where(
                and_(
                    Incident.status_id.in_(active_status_ids),
                    Incident.overdue == False,
                    Incident.sla_deadline < now
                )
            )
        )
        overdue_incidents = result.scalars().all()
        
        logger.info(f"SLA Monitor: Found {len(overdue_incidents)} overdue incidents")
        
        for incident in overdue_incidents:
            # Помечаем как просроченный
            incident.overdue = True
            
            # Считаем часы просрочки
            overdue_hours = (now - incident.sla_deadline).total_seconds() / 3600
            
            # Добавляем запись в историю
            history = IncidentHistory(
                incident_id=incident.id,
                user_id=None,  # Система
                previous_status_id=incident.status_id,
                new_status_id=incident.status_id,
                comment="Автоматическая просрочка по SLA"
            )
            db.add(history)
            
            # Отправляем уведомления
            await _send_overdue_notifications(db, incident, overdue_hours)
        
        await db.commit()
        return {"checked": True, "overdue_found": len(overdue_incidents)}


async def _send_overdue_notifications(db, incident, overdue_hours: float):
    """Send overdue notifications to relevant users"""
    recipients = []
    
    # Get all Admins
    admin_role_result = await db.execute(
        select(Role).where(Role.name == "Admin")
    )
    admin_role = admin_role_result.scalar_one_or_none()
    if admin_role:
        admins_result = await db.execute(
            select(User).where(User.role_id == admin_role.id, User.is_active == True)
        )
        recipients.extend(admins_result.scalars().all())
    
    # Get Manager from incident's department only
    manager_role_result = await db.execute(
        select(Role).where(Role.name == "Manager")
    )
    manager_role = manager_role_result.scalar_one_or_none()
    if manager_role and incident.department_id:
        dept_managers_result = await db.execute(
            select(User).where(
                User.role_id == manager_role.id,
                User.department_id == incident.department_id,
                User.is_active == True
            )
        )
        for manager in dept_managers_result.scalars().all():
            if manager not in recipients:
                recipients.append(manager)
    
    # Add initiator and executor
    if incident.initiator and incident.initiator not in recipients:
        recipients.append(incident.initiator)
    if incident.executor and incident.executor not in recipients:
        recipients.append(incident.executor)
    
    extra = {"overdue_hours": overdue_hours}
    
    for user in recipients:
        await send_notification_with_settings(
            db=db,
            user=user,
            incident=incident,
            event_type="overdue",
            email_type="sla_overdue",
            title=f"Просрочка SLA: Инцидент #{str(incident.id)[:8]}",
            message=f"Инцидент '{incident.title}' превысил установленный SLA на {overdue_hours:.1f} ч.",
            extra=extra
        )


@celery_app.task(name="shared.tasks.check_escalation")
def check_escalation():
    """
    Проверка инцидентов для эскалации (каждые 5 мин).
    
    L1: 80% SLA — уведомление Manager/Admin
    L2: просрочка — обрабатывается в check_sla_overdue
    """
    import asyncio
    return asyncio.run(_check_escalation_async())


async def _check_escalation_async():
    async with async_session() as db:
        # Получаем активные статусы
        active_status_names = ["Новый", "Назначен", "В работе"]
        status_result = await db.execute(
            select(Status).where(Status.name.in_(active_status_names))
        )
        active_statuses = status_result.scalars().all()
        active_status_ids = [s.id for s in active_statuses]
        
        # Получаем правила эскалации
        rules_result = await db.execute(
            select(EscalationRule).where(EscalationRule.is_active == True)
        )
        rules = rules_result.scalars().all()
        
        # Находим активные инциденты
        result = await db.execute(
            select(Incident)
            .options(
                selectinload(Incident.status),
                selectinload(Incident.initiator),
                selectinload(Incident.executor),
                selectinload(Incident.priority),
                selectinload(Incident.category),
                selectinload(Incident.department)
            )
            .where(Incident.status_id.in_(active_status_ids))
        )
        incidents = result.scalars().all()
        
        escalated_count = 0
        
        for incident in incidents:
            # Считаем % использования SLA
            if incident.sla_deadline:
                sla_percentage = get_sla_percentage(
                    incident.created_at,
                    incident.sla_deadline,
                    incident.resolved_at,
                    incident.closed_at
                )
                
                # Level 1: 80% SLA (предупреждение)
                if sla_percentage >= 80 and not incident.overdue:
                    await _escalate_level_1(db, incident, rules, sla_percentage)
                    escalated_count += 1
                
                # Level 2 (просрочка) обрабатывается отдельно в check_sla_overdue
                # Дублирующих уведомлений не отправляем
        
        await db.commit()
        return {"checked": True, "escalated": escalated_count}


async def _escalate_level_1(db, incident, rules, sla_percentage: float):
    """Level 1 escalation: 80% SLA passed"""
    # Find Level 1 rule
    level_1_rule = None
    for rule in rules:
        if rule.level == 1 and rule.condition_type == "percent_80":
            level_1_rule = rule
            break
    
    if not level_1_rule:
        return
    
    recipients = []
    
    # Get role info
    role_result = await db.execute(
        select(Role).where(Role.id == level_1_rule.notify_role_id)
    )
    notify_role = role_result.scalar_one_or_none()
    
    if notify_role:
        if notify_role.name == "Manager":
            # Only managers from incident's department
            if incident.department_id:
                users_result = await db.execute(
                    select(User)
                    .options(selectinload(User.role))
                    .where(
                        User.role_id == level_1_rule.notify_role_id,
                        User.department_id == incident.department_id,
                        User.is_active == True
                    )
                )
                recipients = list(users_result.scalars().all())
        elif notify_role.name == "Admin":
            # Admins get all escalation notifications
            users_result = await db.execute(
                select(User)
                .options(selectinload(User.role))
                .where(User.role_id == level_1_rule.notify_role_id, User.is_active == True)
            )
            recipients = list(users_result.scalars().all())
    
    # Also notify executor if assigned
    if incident.executor and incident.executor not in recipients:
        recipients.append(incident.executor)
    
    extra = {"percent_used": sla_percentage}
    
    for user in recipients:
        # Check if notification already sent (avoid duplicates)
        existing = await db.execute(
            select(Notification).where(
                Notification.incident_id == incident.id,
                Notification.user_id == user.id,
                Notification.type == "escalation",
                Notification.title.ilike("%L1%")
            )
        )
        if existing.scalar_one_or_none():
            continue
        
        await send_notification_with_settings(
            db=db,
            user=user,
            incident=incident,
            event_type="escalation",
            email_type="escalation_level1",
            title=f"Эскалация L1: Инцидент #{str(incident.id)[:8]}",
            message=f"Инцидент '{incident.title}' достиг {sla_percentage:.0f}% времени SLA. Требуется внимание.",
            extra=extra
        )


@celery_app.task(name="shared.tasks.send_notification")
def send_notification(user_id: str, incident_id: str = None, 
                      type: str = "info", title: str = "", message: str = ""):
    """Отправка уведомления конкретному пользователю."""
    import asyncio
    return asyncio.run(_send_notification_async(user_id, incident_id, type, title, message))


async def _send_notification_async(user_id: str, incident_id: str, 
                                    type: str, title: str, message: str):
    async with async_session() as db:
        notification = Notification(
            user_id=UUID(user_id),
            incident_id=UUID(incident_id) if incident_id else None,
            type=type,
            title=title,
            message=message
        )
        db.add(notification)
        await db.commit()
        return {"sent": True, "user_id": user_id}


@celery_app.task(name="shared.tasks.notify_incident_created")
def notify_incident_created(incident_id: str):
    """
    Уведомление о новом инциденте.
    
    Получатели: Manager отдела, Admin, Executor'ы отдела.
    """
    import asyncio
    return asyncio.run(_notify_incident_created_async(incident_id))


async def _notify_incident_created_async(incident_id: str):
    """Send notifications when incident is created to managers/admins and department executors"""
    async with async_session() as db:
        # Get incident with relations
        result = await db.execute(
            select(Incident)
            .options(
                selectinload(Incident.initiator),
                selectinload(Incident.executor),
                selectinload(Incident.priority),
                selectinload(Incident.category),
                selectinload(Incident.department)
            )
            .where(Incident.id == UUID(incident_id))
        )
        incident = result.scalar_one_or_none()
        
        if not incident:
            return {"error": "Incident not found"}
        
        recipients = []
        
        # Get managers and admins
        roles_result = await db.execute(
            select(Role).where(Role.name.in_(["Manager", "Admin"]))
        )
        roles = roles_result.scalars().all()
        role_ids = [r.id for r in roles]
        
        # Admins see all incidents, get all notifications
        admin_role_result = await db.execute(
            select(Role).where(Role.name == "Admin")
        )
        admin_role = admin_role_result.scalar_one_or_none()
        
        if admin_role:
            admins_result = await db.execute(
                select(User).where(User.role_id == admin_role.id, User.is_active == True)
            )
            admins = list(admins_result.scalars().all())
            recipients.extend(admins)
        
        # Manager - only from the incident's department
        manager_role_result = await db.execute(
            select(Role).where(Role.name == "Manager")
        )
        manager_role = manager_role_result.scalar_one_or_none()
        
        if manager_role and incident.department_id:
            managers_result = await db.execute(
                select(User).where(
                    User.role_id == manager_role.id,
                    User.department_id == incident.department_id,
                    User.is_active == True
                )
            )
            department_managers = list(managers_result.scalars().all())
            for manager in department_managers:
                if manager not in recipients:
                    recipients.append(manager)
        
        # Get executors from the incident's department
        executor_role_result = await db.execute(
            select(Role).where(Role.name == "Executor")
        )
        executor_role = executor_role_result.scalar_one_or_none()
        
        if executor_role and incident.department_id:
            executors_result = await db.execute(
                select(User).where(
                    User.role_id == executor_role.id,
                    User.department_id == incident.department_id,
                    User.is_active == True
                )
            )
            department_executors = list(executors_result.scalars().all())
            # Add executors not already in recipients
            for executor in department_executors:
                if executor not in recipients:
                    recipients.append(executor)
        
        for user in recipients:
            await send_notification_with_settings(
                db=db,
                user=user,
                incident=incident,
                event_type="incident_created",
                email_type="incident_created",
                title=f"Новый инцидент #{str(incident.id)[:8]}",
                message=f"Создан инцидент: {incident.title}"
            )
        
        await db.commit()
        return {"sent": True, "recipients": len(recipients)}


@celery_app.task(name="shared.tasks.notify_incident_assigned")
def notify_incident_assigned(incident_id: str, executor_id: str, assigned_by_id: str = None):
    """
    Уведомление о назначении исполнителя.
    
    Получатели: исполнитель, Manager отдела, Admin (кроме назначившего).
    """
    import asyncio
    return asyncio.run(_notify_incident_assigned_async(incident_id, executor_id, assigned_by_id))


async def _notify_incident_assigned_async(incident_id: str, executor_id: str, assigned_by_id: str):
    """Send notification about incident assignment to executor, manager, and admins"""
    async with async_session() as db:
        # Get incident with relations
        result = await db.execute(
            select(Incident)
            .options(
                selectinload(Incident.initiator),
                selectinload(Incident.executor),
                selectinload(Incident.priority),
                selectinload(Incident.category),
                selectinload(Incident.department)
            )
            .where(Incident.id == UUID(incident_id))
        )
        incident = result.scalar_one_or_none()
        
        if not incident:
            return {"error": "Incident not found"}
        
        # Get executor
        executor_result = await db.execute(
            select(User).where(User.id == UUID(executor_id))
        )
        executor = executor_result.scalar_one_or_none()
        
        if not executor:
            return {"error": "Executor not found"}
        
        recipients = []
        
        # Get Admins (all)
        admin_role_result = await db.execute(
            select(Role).where(Role.name == "Admin")
        )
        admin_role = admin_role_result.scalar_one_or_none()
        
        if admin_role:
            admins_result = await db.execute(
                select(User).where(User.role_id == admin_role.id, User.is_active == True)
            )
            admins = list(admins_result.scalars().all())
            # Exclude assigned_by from admins
            for admin in admins:
                if assigned_by_id and str(admin.id) != assigned_by_id and admin not in recipients:
                    recipients.append(admin)
        
        # Get Manager from incident's department (exclude assigned_by)
        manager_role_result = await db.execute(
            select(Role).where(Role.name == "Manager")
        )
        manager_role = manager_role_result.scalar_one_or_none()
        
        if manager_role and incident.department_id:
            managers_result = await db.execute(
                select(User).where(
                    User.role_id == manager_role.id,
                    User.department_id == incident.department_id,
                    User.is_active == True
                )
            )
            for manager in managers_result.scalars().all():
                if assigned_by_id and str(manager.id) != assigned_by_id and manager not in recipients:
                    recipients.append(manager)
        
        # Add initiator (notify about who will work on their incident)
        # Инициатор всегда получает уведомление о назначении исполнителя,
        # если только он сам не является исполнителем (в этом случае получит как исполнитель)
        if incident.initiator and str(incident.initiator.id) != str(executor.id) and incident.initiator not in recipients:
            recipients.append(incident.initiator)
        
        # Add executor (always notify, unless they are the one who assigned)
        if executor and str(executor.id) != assigned_by_id and executor not in recipients:
            recipients.append(executor)
        
        if not recipients:
            return {"sent": False, "reason": "No recipients"}
        
        extra = {"executor_name": executor.full_name, "assigned_by_id": assigned_by_id}
        
        for user in recipients:
            # Персонализируем сообщение в зависимости от получателя
            if str(user.id) == str(executor.id):
                # Исполнителю: "Вы назначены"
                title = f"Вы назначены на инцидент #{str(incident.id)[:8]}"
                message = f"Вы назначены исполнителем на инцидент: {incident.title}"
            elif str(user.id) == str(incident.initiator_id):
                # Инициатору: "Назначен исполнитель <имя>"
                title = f"На инцидент назначен исполнитель"
                message = f"На ваш инцидент \"{incident.title}\" назначен исполнитель: {executor.full_name}"
            else:
                # Админу/Менеджеру: "Назначен исполнитель <имя>"
                title = f"Назначен исполнитель: {executor.full_name}"
                message = f"На инцидент \"{incident.title}\" назначен исполнитель: {executor.full_name}"
            
            await send_notification_with_settings(
                db=db,
                user=user,
                incident=incident,
                event_type="assigned_executor",
                email_type="assigned_executor",
                title=title,
                message=message,
                extra=extra
            )
        
        await db.commit()
        return {"sent": True, "recipients": len(recipients)}


@celery_app.task(name="shared.tasks.notify_status_changed")
def notify_status_changed(incident_id: str, old_status: str, new_status: str, 
                          comment: str = "", changed_by_id: str = None):
    """
    Уведомление о смене статуса.
    
    Получатели: инициатор и исполнитель (кроме того, кто изменил).
    """
    import asyncio
    return asyncio.run(_notify_status_changed_async(
        incident_id, old_status, new_status, comment, changed_by_id
    ))


async def _notify_status_changed_async(incident_id: str, old_status: str, 
                                        new_status: str, comment: str, changed_by_id: str):
    """Send notification about status change (excluding the one who changed it)"""
    async with async_session() as db:
        # Get incident with relations
        result = await db.execute(
            select(Incident)
            .options(
                selectinload(Incident.initiator),
                selectinload(Incident.executor),
                selectinload(Incident.priority),
                selectinload(Incident.category),
                selectinload(Incident.department)
            )
            .where(Incident.id == UUID(incident_id))
        )
        incident = result.scalar_one_or_none()
        
        if not incident:
            return {"error": "Incident not found"}
        
        recipients = []
        
        # Notify initiator (if not the one who changed status)
        if incident.initiator and str(incident.initiator.id) != changed_by_id:
            recipients.append(incident.initiator)
        
        # Notify executor (if not the one who changed status)
        if incident.executor and str(incident.executor.id) != changed_by_id and incident.executor not in recipients:
            recipients.append(incident.executor)
        
        if not recipients:
            return {"sent": False, "reason": "No recipients (only changer would be notified)"}
        
        extra = {"old_status": old_status, "new_status": new_status, "comment": comment}
        
        for user in recipients:
            await send_notification_with_settings(
                db=db,
                user=user,
                incident=incident,
                event_type="status_changed",
                email_type="status_changed",
                title=f"Статус изменён: {old_status} → {new_status}",
                message=f"Инцидент #{str(incident.id)[:8]}: {incident.title}",
                extra=extra
            )
        
        await db.commit()
        return {"sent": True, "recipients": len(recipients)}


async def _notify_new_comment_async(incident_id: str, author_id: str, comment_content: str):
    """Send notification about new comment to initiator and executor"""
    async with async_session() as db:
        # Get incident with relations
        result = await db.execute(
            select(Incident)
            .options(
                selectinload(Incident.initiator),
                selectinload(Incident.executor),
                selectinload(Incident.priority),
                selectinload(Incident.category),
                selectinload(Incident.department)
            )
            .where(Incident.id == UUID(incident_id))
        )
        incident = result.scalar_one_or_none()
        
        if not incident:
            return {"error": "Incident not found"}
        
        # Get author
        author_result = await db.execute(
            select(User).where(User.id == UUID(author_id))
        )
        author = author_result.scalar_one_or_none()
        author_name = author.full_name if author else "Пользователь"
        
        # Notify initiator and executor (excluding comment author)
        recipients = []
        
        if incident.initiator and str(incident.initiator.id) != author_id:
            recipients.append(incident.initiator)
        
        if incident.executor and str(incident.executor.id) != author_id and incident.executor not in recipients:
            recipients.append(incident.executor)
        
        if not recipients:
            return {"sent": False, "reason": "No recipients"}
        
        extra = {"author": author_name, "comment": comment_content[:200]}
        
        for user in recipients:
            # For comments, always send regardless of settings (mandatory)
            await send_internal_notification(
                db=db,
                user_id=user.id,
                incident_id=incident.id,
                type="new_comment",
                title=f"Новый комментарий от {author_name}",
                message=f"Инцидент #{str(incident.id)[:8]}: {comment_content[:100]}..."
            )
            # Send email
            await send_email_notification(
                user=user,
                incident=incident,
                email_type="new_comment",
                extra=extra
            )
        
        await db.commit()
        return {"sent": True, "recipients": len(recipients)}


async def _notify_incident_resolved_async(incident_id: str, resolved_by_id: str, comment: str):
    """Send notification about resolved incident"""
    async with async_session() as db:
        # Get incident with relations
        result = await db.execute(
            select(Incident)
            .options(
                selectinload(Incident.initiator),
                selectinload(Incident.executor),
                selectinload(Incident.priority),
                selectinload(Incident.category),
                selectinload(Incident.department)
            )
            .where(Incident.id == UUID(incident_id))
        )
        incident = result.scalar_one_or_none()
        
        if not incident:
            return {"error": "Incident not found"}
        
        recipients = []
        
        # Notify initiator (if not the one who resolved)
        if incident.initiator and str(incident.initiator.id) != resolved_by_id:
            recipients.append(incident.initiator)
        
        # Notify executor (if not the one who resolved and not already in recipients)
        if incident.executor and str(incident.executor.id) != resolved_by_id and incident.executor not in recipients:
            recipients.append(incident.executor)
        
        # Notify department manager (if exists and not already in recipients)
        if incident.department and incident.department.manager_id:
            manager_result = await db.execute(
                select(User).where(User.id == incident.department.manager_id, User.is_active == True)
            )
            manager = manager_result.scalar_one_or_none()
            if manager and manager not in recipients:
                recipients.append(manager)
        
        if not recipients:
            return {"sent": False, "reason": "No recipients"}
        
        extra = {"comment": comment}
        
        for user in recipients:
            await send_notification_with_settings(
                db=db,
                user=user,
                incident=incident,
                event_type="incident_resolved",
                email_type="incident_resolved",
                title=f"Инцидент решён: #{str(incident.id)[:8]}",
                message=f"Инцидент '{incident.title}' был решён.",
                extra=extra
            )
        
        await db.commit()
        return {"sent": True, "recipients": len(recipients)}


async def _notify_incident_closed_async(incident_id: str, closed_by_id: str):
    """Send notification about closed incident"""
    async with async_session() as db:
        # Get incident with relations
        result = await db.execute(
            select(Incident)
            .options(
                selectinload(Incident.initiator),
                selectinload(Incident.executor),
                selectinload(Incident.priority),
                selectinload(Incident.category),
                selectinload(Incident.department)
            )
            .where(Incident.id == UUID(incident_id))
        )
        incident = result.scalar_one_or_none()
        
        if not incident:
            return {"error": "Incident not found"}
        
        recipients = []
        
        # Notify initiator (if not the one who closed)
        if incident.initiator and str(incident.initiator.id) != closed_by_id:
            recipients.append(incident.initiator)
        
        # Notify executor (if not the one who closed)
        if incident.executor and str(incident.executor.id) != closed_by_id and incident.executor not in recipients:
            recipients.append(incident.executor)
        
        if not recipients:
            return {"sent": False, "reason": "No recipients"}
        
        for user in recipients:
            await send_notification_with_settings(
                db=db,
                user=user,
                incident=incident,
                event_type="incident_resolved",
                email_type="incident_closed",
                title=f"Инцидент закрыт: #{str(incident.id)[:8]}",
                message=f"Инцидент '{incident.title}' был закрыт."
            )
        
        await db.commit()
        return {"sent": True, "recipients": len(recipients)}


@celery_app.task(name="shared.tasks.notify_priority_changed")
def notify_priority_changed(incident_id: str, old_priority: str, 
                             new_priority: str, new_deadline: str = None,
                             changed_by_id: str = None):
    """
    Уведомление об изменении приоритета.
    
    Получатели: инициатор и исполнитель (кроме того, кто изменил).
    """
    import asyncio
    return asyncio.run(_notify_priority_changed_async(
        incident_id, old_priority, new_priority, new_deadline, changed_by_id
    ))


async def _notify_priority_changed_async(incident_id: str, old_priority: str, 
                                          new_priority: str, new_deadline: str,
                                          changed_by_id: str):
    """Send notification about priority change"""
    async with async_session() as db:
        # Get incident with relations
        result = await db.execute(
            select(Incident)
            .options(
                selectinload(Incident.initiator),
                selectinload(Incident.executor),
                selectinload(Incident.priority),
                selectinload(Incident.category),
                selectinload(Incident.department)
            )
            .where(Incident.id == UUID(incident_id))
        )
        incident = result.scalar_one_or_none()
        
        if not incident:
            return {"error": "Incident not found"}
        
        recipients = []
        
        # Notify initiator (if not the one who changed)
        if incident.initiator and str(incident.initiator.id) != changed_by_id:
            recipients.append(incident.initiator)
        
        # Notify executor (if not the one who changed)
        if incident.executor and str(incident.executor.id) != changed_by_id and incident.executor not in recipients:
            recipients.append(incident.executor)
        
        if not recipients:
            return {"sent": False, "reason": "No recipients"}
        
        extra = {
            "old_priority": old_priority,
            "new_priority": new_priority,
            "new_deadline": new_deadline
        }
        
        for user in recipients:
            await send_notification_with_settings(
                db=db,
                user=user,
                incident=incident,
                event_type="priority_changed",
                email_type="priority_changed",
                title=f"Приоритет изменён: {old_priority} → {new_priority}",
                message=f"Инцидент #{str(incident.id)[:8]}: {incident.title}",
                extra=extra
            )
        
        await db.commit()
        return {"sent": True, "recipients": len(recipients)}