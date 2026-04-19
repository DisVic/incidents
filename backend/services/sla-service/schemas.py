"""
Схемы Pydantic для SLA Service
"""
import uuid
from typing import Optional
from pydantic import BaseModel


class SLAPolicyCreate(BaseModel):
    """Создание SLA-политики"""
    priority_id: uuid.UUID  # ID приоритета
    resolution_hours: int  # Время решения в часах
    description: Optional[str] = None  # Описание


class SLAPolicyResponse(BaseModel):
    """Ответ с данными SLA-политики"""
    id: uuid.UUID
    priority_id: uuid.UUID
    resolution_hours: int
    description: Optional[str]
    
    class Config:
        from_attributes = True


class EscalationRuleCreate(BaseModel):
    """Создание правила эскалации"""
    level: int  # Уровень эскалации
    notify_role_id: uuid.UUID  # ID роли для уведомления
    condition_type: str  # Тип условия


class EscalationRuleResponse(BaseModel):
    """Ответ с данными правила эскалации"""
    id: uuid.UUID
    level: int
    notify_role_id: uuid.UUID
    condition_type: str
    is_active: bool  # Активность правила
    
    class Config:
        from_attributes = True
