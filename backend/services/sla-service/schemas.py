"""
Pydantic-схемы для SLA Service.

Классы:
- SLAPolicyCreate/Response: создание и ответ политики SLA
- EscalationRuleCreate/Response: создание и ответ правила эскалации
"""
import uuid
from typing import Optional
from pydantic import BaseModel


class SLAPolicyCreate(BaseModel):
    """Создание SLA-политики для приоритета."""
    priority_id: uuid.UUID
    resolution_days: int  # Время на решение в днях
    description: Optional[str] = None


class SLAPolicyResponse(BaseModel):
    """Данные SLA-политики для API-ответа."""
    id: uuid.UUID
    priority_id: uuid.UUID
    resolution_days: int
    description: Optional[str]
    
    class Config:
        from_attributes = True


class EscalationRuleCreate(BaseModel):
    """Создание правила эскалации."""
    level: int  # Уровень эскалации (1=предупреждение, 2=критично)
    notify_role_id: uuid.UUID  # Роль для уведомления (Manager/Admin)
    condition_type: str  # "percent_80" или "overdue"


class EscalationRuleResponse(BaseModel):
    """Данные правила эскалации для API-ответа."""
    id: uuid.UUID
    level: int
    notify_role_id: uuid.UUID
    condition_type: str
    is_active: bool
    
    class Config:
        from_attributes = True
