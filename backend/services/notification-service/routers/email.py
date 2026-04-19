"""
Email notifications via SMTP with HTML templates
"""
from fastapi import APIRouter
from pydantic import BaseModel, EmailStr
from typing import Optional, Dict, Any
from enum import Enum

from shared import settings

router = APIRouter()

# Импорт шаблонов писем
try:
    from templates import (
        template_incident_created,
        template_incident_assigned,
        template_incident_resolved,
        template_incident_closed,
        template_sla_overdue,
        template_escalation_level1,
        template_escalation_level2,
        template_status_changed,
        template_new_comment,
        template_priority_changed,
        template_password_changed,
    )
    TEMPLATES_AVAILABLE = True
except ImportError:
    TEMPLATES_AVAILABLE = False


class EmailType(str, Enum):
    """Типы email-уведомлений"""
    INCIDENT_CREATED = "incident_created"
    INCIDENT_ASSIGNED = "incident_assigned"
    INCIDENT_RESOLVED = "incident_resolved"
    INCIDENT_CLOSED = "incident_closed"
    SLA_OVERDUE = "sla_overdue"
    ESCALATION_LEVEL1 = "escalation_level1"
    ESCALATION_LEVEL2 = "escalation_level2"
    STATUS_CHANGED = "status_changed"
    NEW_COMMENT = "new_comment"
    PRIORITY_CHANGED = "priority_changed"
    PASSWORD_CHANGED = "password_changed"
    CUSTOM = "custom"


class EmailRequest(BaseModel):
    """Запрос на отправку простого письма"""
    to: EmailStr
    subject: str
    body: str
    html_body: Optional[str] = None


class TemplatedEmailRequest(BaseModel):
    """Запрос на отправку письма по шаблону"""
    to: EmailStr
    email_type: EmailType
    incident: Dict[str, Any]
    extra: Optional[Dict[str, Any]] = None
    base_url: Optional[str] = None


def send_smtp_email(to: str, subject: str, body: str, html_body: Optional[str] = None) -> dict:
    """Отправка email через SMTP"""
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    
    if not settings.SMTP_HOST:
        return {"error": "SMTP not configured"}
    
    msg = MIMEMultipart("alternative")
    msg["From"] = settings.SMTP_FROM or settings.SMTP_USER
    msg["To"] = to
    msg["Subject"] = f"[IMS] {subject}"
    
    # Plain text версия
    msg.attach(MIMEText(body, "plain", "utf-8"))
    
    # HTML версия (если есть)
    if html_body:
        msg.attach(MIMEText(html_body, "html", "utf-8"))
    
    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(msg)
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/send")
async def send_email(data: EmailRequest):
    """Отправка простого или HTML письма"""
    result = send_smtp_email(
        to=data.to,
        subject=data.subject,
        body=data.body,
        html_body=data.html_body
    )
    return result


@router.post("/send-templated")
async def send_templated_email(data: TemplatedEmailRequest):
    """Отправка письма по готовому шаблону"""
    if not TEMPLATES_AVAILABLE:
        return {"error": "Templates not available"}
    
    base_url = data.base_url or "http://localhost:3000"
    extra = data.extra or {}
    incident = data.incident
    
    # Генерация HTML из шаблона
    html_body = ""
    subject = ""
    
    if data.email_type == EmailType.INCIDENT_CREATED:
        html_body = template_incident_created(incident, base_url)
        subject = f"Создан инцидент #{incident.get('id', 'N/A')[:8]}"
        
    elif data.email_type == EmailType.INCIDENT_ASSIGNED:
        html_body = template_incident_assigned(incident, base_url)
        subject = "Вам назначен инцидент"
        
    elif data.email_type == EmailType.INCIDENT_RESOLVED:
        html_body = template_incident_resolved(incident, base_url)
        subject = "Инцидент решён"
        
    elif data.email_type == EmailType.INCIDENT_CLOSED:
        html_body = template_incident_closed(incident, base_url)
        subject = "Инцидент закрыт"
        
    elif data.email_type == EmailType.SLA_OVERDUE:
        overdue_hours = extra.get("overdue_hours", 0)
        html_body = template_sla_overdue(incident, overdue_hours, base_url)
        subject = f"ПРОСРОЧКА: Инцидент #{incident.get('id', 'N/A')[:8]}"
        
    elif data.email_type == EmailType.ESCALATION_LEVEL1:
        percent = extra.get("percent_used", 80)
        html_body = template_escalation_level1(incident, percent, base_url)
        subject = f"[ЭСКАЛАЦИЯ] Инцидент #{incident.get('id', 'N/A')[:8]}"
        
    elif data.email_type == EmailType.ESCALATION_LEVEL2:
        overdue_hours = extra.get("overdue_hours", 0)
        html_body = template_escalation_level2(incident, overdue_hours, base_url)
        subject = f"[КРИТИЧНО] Инцидент #{incident.get('id', 'N/A')[:8]} ПРОСРОЧЕН!"
        
    elif data.email_type == EmailType.STATUS_CHANGED:
        old_status = extra.get("old_status", "")
        new_status = extra.get("new_status", "")
        comment = extra.get("comment", "")
        html_body = template_status_changed(incident, old_status, new_status, comment, base_url)
        subject = f"Статус изменён: {old_status} → {new_status}"
        
    elif data.email_type == EmailType.NEW_COMMENT:
        author = extra.get("author", "Пользователь")
        comment = extra.get("comment", "")
        html_body = template_new_comment(incident, author, comment, base_url)
        subject = f"Новый комментарий к инциденту #{incident.get('id', 'N/A')[:8]}"
        
    elif data.email_type == EmailType.PRIORITY_CHANGED:
        old_priority = extra.get("old_priority", "")
        new_priority = extra.get("new_priority", "")
        new_deadline = extra.get("new_deadline", "")
        html_body = template_priority_changed(incident, old_priority, new_priority, new_deadline, base_url)
        subject = f"Приоритет изменён: {old_priority} → {new_priority}"
    
    elif data.email_type == EmailType.PASSWORD_CHANGED:
        html_body = template_password_changed(base_url)
        subject = "Пароль изменён"
    
    else:
        return {"error": f"Unknown email type: {data.email_type}"}
    
    # Plain text версия (резервная)
    plain_body = f"Инцидент: {incident.get('title', 'N/A')}\nОткройте: {base_url}/incidents/{incident.get('id')}"
    
    result = send_smtp_email(
        to=data.to,
        subject=subject,
        body=plain_body,
        html_body=html_body
    )
    
    return result


@router.post("/send-bulk")
async def send_bulk_email(recipients: list[EmailStr], subject: str, body: str, html_body: Optional[str] = None):
    """Массовая рассылка простого письма"""
    results = []
    for email in recipients:
        result = send_smtp_email(
            to=email,
            subject=subject,
            body=body,
            html_body=html_body
        )
        results.append({"email": email, "result": result})
    return {"results": results}


@router.post("/send-bulk-templated")
async def send_bulk_templated_email(recipients: list[EmailStr], email_type: EmailType, incident: Dict[str, Any], extra: Optional[Dict[str, Any]] = None, base_url: Optional[str] = None):
    """Массовая рассылка письма по шаблону"""
    results = []
    for email in recipients:
        result = await send_templated_email(TemplatedEmailRequest(
            to=email,
            email_type=email_type,
            incident=incident,
            extra=extra,
            base_url=base_url
        ))
        results.append({"email": email, "result": result})
    return {"results": results}