"""
HTML Email Templates for Incident Management System
"""

from typing import Optional


def get_base_styles() -> str:
    """Base CSS styles for email templates"""
    return """
        body { font-family: 'Segoe UI', Arial, sans-serif; margin: 0; padding: 0; background: #f5f5f5; }
        .container { max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
        .header { background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%); color: white; padding: 24px; }
        .header h1 { margin: 0; font-size: 20px; font-weight: 600; }
        .header .subtitle { margin-top: 4px; font-size: 14px; opacity: 0.9; }
        .content { padding: 24px; }
        .incident-info { background: #f8fafc; border-radius: 8px; padding: 16px; margin: 16px 0; }
        .info-row { display: flex; padding: 8px 0; border-bottom: 1px solid #e2e8f0; }
        .info-row:last-child { border-bottom: none; }
        .info-label { width: 120px; color: #64748b; font-size: 14px; }
        .info-value { flex: 1; color: #1e293b; font-size: 14px; }
        .priority-critical { color: #dc2626; font-weight: 600; }
        .priority-high { color: #ea580c; font-weight: 600; }
        .priority-medium { color: #2563eb; }
        .priority-low { color: #64748b; }
        .status-badge { display: inline-block; padding: 4px 12px; border-radius: 12px; font-size: 12px; font-weight: 500; }
        .btn { display: inline-block; padding: 12px 24px; background: #3b82f6; color: white; text-decoration: none; border-radius: 6px; font-weight: 500; margin-top: 16px; }
        .btn:hover { background: #2563eb; }
        .warning { background: #fef3c7; border-left: 4px solid #f59e0b; padding: 12px 16px; margin: 16px 0; border-radius: 0 8px 8px 0; }
        .danger { background: #fee2e2; border-left: 4px solid #dc2626; padding: 12px 16px; margin: 16px 0; border-radius: 0 8px 8px 0; }
        .footer { background: #f8fafc; padding: 16px 24px; text-align: center; color: #64748b; font-size: 12px; border-top: 1px solid #e2e8f0; }
        .footer a { color: #3b82f6; }
    """


def render_email(
    title: str,
    subtitle: str,
    content: str,
    button_url: Optional[str] = None,
    button_text: str = "Открыть инцидент",
    warning: Optional[str] = None,
    danger: Optional[str] = None
) -> str:
    """Render email with base template"""
    warning_html = f'<div class="warning">{warning}</div>' if warning else ''
    danger_html = f'<div class="danger">{danger}</div>' if danger else ''
    button_html = f'<a href="{button_url}" class="btn">{button_text}</a>' if button_url else ''
    
    return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>{get_base_styles()}</style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{title}</h1>
            <div class="subtitle">{subtitle}</div>
        </div>
        <div class="content">
            {warning_html}
            {danger_html}
            {content}
            {button_html}
        </div>
        <div class="footer">
            <p>Это автоматическое уведомление. Не отвечайте на это письмо.</p>
            <p>Система управления инцидентами</p>
        </div>
    </div>
</body>
</html>
    """


def format_datetime(dt_str: str) -> str:
    """Format datetime string for display"""
    if not dt_str:
        return "—"
    try:
        from datetime import datetime
        dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        return dt.strftime('%d.%m.%Y %H:%M')
    except:
        return dt_str


def get_priority_class(priority: str) -> str:
    """Get CSS class for priority"""
    priority_lower = priority.lower() if priority else ''
    if 'критич' in priority_lower:
        return 'priority-critical'
    elif 'высок' in priority_lower:
        return 'priority-high'
    elif 'средн' in priority_lower:
        return 'priority-medium'
    return 'priority-low'


def incident_info_block(incident: dict) -> str:
    """Generate incident info HTML block"""
    return f"""
    <div class="incident-info">
        <div class="info-row">
            <div class="info-label">ID:</div>
            <div class="info-value">#{incident.get('id', 'N/A')[:8]}</div>
        </div>
        <div class="info-row">
            <div class="info-label">Заголовок:</div>
            <div class="info-value">{incident.get('title', 'N/A')}</div>
        </div>
        <div class="info-row">
            <div class="info-label">Приоритет:</div>
            <div class="info-value {get_priority_class(incident.get('priority_name'))}">{incident.get('priority_name', 'N/A')}</div>
        </div>
        <div class="info-row">
            <div class="info-label">Категория:</div>
            <div class="info-value">{incident.get('category_name', 'N/A')}</div>
        </div>
        <div class="info-row">
            <div class="info-label">Отдел:</div>
            <div class="info-value">{incident.get('department_name', 'N/A')}</div>
        </div>
        <div class="info-row">
            <div class="info-label">Инициатор:</div>
            <div class="info-value">{incident.get('initiator_name', 'N/A')}</div>
        </div>
        <div class="info-row">
            <div class="info-label">Исполнитель:</div>
            <div class="info-value">{incident.get('executor_name') or 'Не назначен'}</div>
        </div>
        <div class="info-row">
            <div class="info-label">Дедлайн SLA:</div>
            <div class="info-value">{format_datetime(incident.get('sla_deadline'))}</div>
        </div>
    </div>
    """


# ============================================
# SPECIFIC EMAIL TEMPLATES
# ============================================

def template_incident_created(incident: dict, base_url: str = "http://localhost:3000") -> str:
    """Email template for incident created notification"""
    content = f"""
    <p>Добрый день!</p>
    <p>Создан новый инцидент, требующий внимания:</p>
    {incident_info_block(incident)}
    """
    return render_email(
        title="Создан новый инцидент",
        subtitle=f"Инцидент #{incident.get('id', 'N/A')[:8]}",
        content=content,
        button_url=f"{base_url}/incidents/{incident.get('id')}"
    )


def template_incident_assigned(incident: dict, base_url: str = "http://localhost:3000") -> str:
    """Email template for incident assigned notification"""
    content = f"""
    <p>Добрый день!</p>
    <p>Вам назначен инцидент для решения:</p>
    {incident_info_block(incident)}
    <p>Пожалуйста, примите инцидент в работу в ближайшее время.</p>
    """
    return render_email(
        title="Вам назначен инцидент",
        subtitle="Требуется ваше внимание",
        content=content,
        button_url=f"{base_url}/incidents/{incident.get('id')}"
    )


def template_incident_resolved(incident: dict, base_url: str = "http://localhost:3000") -> str:
    """Email template for incident resolved notification"""
    content = f"""
    <p>Добрый день!</p>
    <p>Инцидент был отмечен как решённый. Пожалуйста, подтвердите закрытие:</p>
    {incident_info_block(incident)}
    <p>Если проблема не решена, вы можете оставить комментарий.</p>
    """
    return render_email(
        title="Инцидент решён",
        subtitle="Требуется подтверждение",
        content=content,
        button_url=f"{base_url}/incidents/{incident.get('id')}"
    )


def template_incident_closed(incident: dict, base_url: str = "http://localhost:3000") -> str:
    """Email template for incident closed notification"""
    content = f"""
    <p>Добрый день!</p>
    <p>Инцидент был закрыт:</p>
    {incident_info_block(incident)}
    """
    return render_email(
        title="Инцидент закрыт",
        subtitle=f"Инцидент #{incident.get('id', 'N/A')[:8]}",
        content=content,
        button_url=f"{base_url}/incidents/{incident.get('id')}"
    )


def template_sla_overdue(incident: dict, overdue_hours: float = 0, base_url: str = "http://localhost:3000") -> str:
    """Email template for SLA overdue notification"""
    content = f"""
    <p>Добрый день!</p>
    <p><strong>Инцидент превысил установленный SLA!</strong></p>
    {incident_info_block(incident)}
    <p><strong>Просрочка: {overdue_hours:.1f} ч.</strong></p>
    <p>Требуется немедленное вмешательство!</p>
    """
    return render_email(
        title="ПРОСРОЧКА SLA",
        subtitle="Требуется срочное внимание",
        content=content,
        button_url=f"{base_url}/incidents/{incident.get('id')}",
        danger=f"Инцидент просрочен на {overdue_hours:.1f} часов!"
    )


def template_escalation_level1(incident: dict, percent_used: float = 80, base_url: str = "http://localhost:3000") -> str:
    """Email template for escalation level 1 notification (80% SLA)"""
    content = f"""
    <p>Добрый день!</p>
    <p>Инцидент использовал {percent_used:.0f}% времени SLA и требует вашего внимания:</p>
    {incident_info_block(incident)}
    <p>Рекомендуется проверить статус и при необходимости помочь исполнителю.</p>
    """
    return render_email(
        title="ЭСКАЛАЦИЯ Уровень 1",
        subtitle="Требуется внимание руководителя",
        content=content,
        button_url=f"{base_url}/incidents/{incident.get('id')}",
        warning=f"Использовано {percent_used:.0f}% времени SLA"
    )


def template_escalation_level2(incident: dict, overdue_hours: float = 0, base_url: str = "http://localhost:3000") -> str:
    """Email template for escalation level 2 notification (overdue)"""
    content = f"""
    <p>Добрый день!</p>
    <p><strong>КРИТИЧНО: Инцидент просрочен и требует НЕМЕДЛЕННОГО вмешательства!</strong></p>
    {incident_info_block(incident)}
    <p><strong>Просрочка: {overdue_hours:.1f} ч.</strong></p>
    <p>Рекомендуемые действия:</p>
    <ul>
        <li>Проверить наличие исполнителя</li>
        <li>Оценить приоритет</li>
        <li>Помочь в решении или переназначить</li>
    </ul>
    """
    return render_email(
        title="КРИТИЧНО: ЭСКАЛАЦИЯ Уровень 2",
        subtitle="Просроченный инцидент",
        content=content,
        button_url=f"{base_url}/incidents/{incident.get('id')}",
        danger=f"Просрочка: {overdue_hours:.1f} часов. Требуется немедленное действие!"
    )


def template_status_changed(incident: dict, old_status: str, new_status: str, comment: str = "", base_url: str = "http://localhost:3000") -> str:
    """Email template for status changed notification"""
    comment_html = f'<p><strong>Комментарий:</strong> {comment}</p>' if comment else ''
    content = f"""
    <p>Добрый день!</p>
    <p>Статус инцидента изменён:</p>
    {incident_info_block(incident)}
    <p><strong>{old_status}</strong> → <strong>{new_status}</strong></p>
    {comment_html}
    """
    return render_email(
        title="Изменён статус инцидента",
        subtitle=f"{old_status} → {new_status}",
        content=content,
        button_url=f"{base_url}/incidents/{incident.get('id')}"
    )


def template_new_comment(incident: dict, author: str, comment: str, base_url: str = "http://localhost:3000") -> str:
    """Email template for new comment notification"""
    content = f"""
    <p>Добрый день!</p>
    <p><strong>{author}</strong> оставил комментарий к инциденту:</p>
    {incident_info_block(incident)}
    <div style="background: #f8fafc; padding: 12px; border-radius: 8px; margin: 16px 0;">
        <p style="margin: 0;">{comment}</p>
    </div>
    """
    return render_email(
        title="Новый комментарий",
        subtitle=f"Инцидент #{incident.get('id', 'N/A')[:8]}",
        content=content,
        button_url=f"{base_url}/incidents/{incident.get('id')}"
    )


def template_priority_changed(incident: dict, old_priority: str, new_priority: str, new_deadline: str = "", base_url: str = "http://localhost:3000") -> str:
    """Email template for priority changed notification"""
    deadline_html = f'<p><strong>Новый дедлайн:</strong> {format_datetime(new_deadline)}</p>' if new_deadline else ''
    content = f"""
    <p>Добрый день!</p>
    <p>Приоритет инцидента изменён:</p>
    {incident_info_block(incident)}
    <p><strong>{old_priority}</strong> → <strong class="{get_priority_class(new_priority)}">{new_priority}</strong></p>
    {deadline_html}
    """
    return render_email(
        title="Изменён приоритет инцидента",
        subtitle=f"{old_priority} → {new_priority}",
        content=content,
        button_url=f"{base_url}/incidents/{incident.get('id')}"
    )


def template_password_changed(base_url: str = "http://localhost:3000") -> str:
    """Email template for password change notification"""
    content = f"""
    <p>Добрый день!</p>
    <p>Ваш пароль был успешно изменён.</p>
    <p>Если это были не вы, немедленно свяжитесь с администратором системы.</p>
    <div style="background: #fef3c7; padding: 12px; border-radius: 8px; margin: 16px 0; border-left: 4px solid #f59e0b;">
        <p style="margin: 0; color: #92400e;"><strong>Внимание!</strong> Если вы не меняли пароль, ваш аккаунт мог быть скомпрометирован.</p>
    </div>
    """
    return render_email(
        title="Пароль изменён",
        subtitle="Уведомление безопасности",
        content=content,
        button_url=base_url
    )
