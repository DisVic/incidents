"""
API управления правилами эскалации и мониторинг.

Эскалация — автоматическое уведомление руководителей при:
- L1: 80% времени SLA использовано (предупреждение)
- L2: инцидент просрочен (критично)

Endpoint'ы:
- GET /escalation/rules — список правил эскалации
- POST /escalation/rules — создать правило
- POST /escalation/check — проверить инциденты на эскалацию
"""
import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from shared import get_db, get_sla_percentage
from shared.models import EscalationRule, Incident, Status, Notification, User
from schemas import EscalationRuleCreate, EscalationRuleResponse

router = APIRouter()


@router.get("/rules")
async def list_rules(db: AsyncSession = Depends(get_db)):
    """Список активных правил эскалации."""
    result = await db.execute(select(EscalationRule).where(EscalationRule.is_active == True))
    return result.scalars().all()


@router.post("/rules", response_model=EscalationRuleResponse)
async def create_rule(data: EscalationRuleCreate, db: AsyncSession = Depends(get_db)):
    """Создание правила эскалации."""
    rule = EscalationRule(
        level=data.level,
        notify_role_id=data.notify_role_id,
        condition_type=data.condition_type
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return rule


@router.post("/check")
async def check_escalation(db: AsyncSession = Depends(get_db)):
    """
    Проверка всех активных инцидентов на условия эскалации.
    
    Алгоритм:
    1. Получает все активные инциденты (не закрытые)
    2. Для каждого считает % использования SLA
    3. Применяет правила эскалации (L1: 80%, L2: overdue)
    4. Создаёт уведомления для указанной роли (Manager/Admin)
    
    Returns:
        dict: {"checked": N, "escalated": M}
    """
    from datetime import datetime
    from shared import settings
    
    # Получаем статус "Закрыт" для фильтрации
    closed = await db.execute(select(Status).where(Status.name == "Закрыт"))
    closed_status = closed.scalar_one_or_none()
    
    # Получаем активные инциденты
    query = select(Incident)
    if closed_status:
        query = query.where(Incident.status_id != closed_status.id)
    
    result = await db.execute(query)
    incidents = result.scalars().all()
    
    # Получаем активные правила эскалации
    rules_result = await db.execute(select(EscalationRule).where(EscalationRule.is_active == True))
    rules = rules_result.scalars().all()
    
    escalated = []
    now = datetime.utcnow()
    
    for incident in incidents:
        # Считаем % использования SLA
        sla_percent = get_sla_percentage(incident.created_at, incident.sla_deadline)
        
        for rule in rules:
            should_escalate = False
            
            # L1: 80% SLA использовано, но ещё не просрочен
            if rule.condition_type == "percent_80" and sla_percent >= 80 and not incident.overdue:
                should_escalate = True
            # L2: инцидент просрочен
            elif rule.condition_type == "overdue" and incident.overdue:
                should_escalate = True
            
            if should_escalate:
                # Получаем пользователей для уведомления
                users_result = await db.execute(
                    select(User).where(User.role_id == rule.notify_role_id, User.is_active == True)
                )
                users = users_result.scalars().all()
                
                # Создаём уведомления
                for user in users:
                    notif = Notification(
                        user_id=user.id,
                        incident_id=incident.id,
                        type="escalation",
                        title=f"Эскалация уровня {rule.level}",
                        message=f"Инцидент #{str(incident.id)[:8]} требует внимания"
                    )
                    db.add(notif)
                
                escalated.append(str(incident.id))
    
    await db.commit()
    return {"checked": len(incidents), "escalated": len(escalated)}
