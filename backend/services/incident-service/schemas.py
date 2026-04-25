"""
Pydantic-схемы для Incident Service.

Разделы:
- Инциденты: IncidentBase, IncidentCreate, IncidentUpdate, IncidentResponse
- Операции: StatusChange, AssignExecutor, TakeIncident, CloseIncident, UpdateDeadline
- Справочники: CategoryResponse, PriorityResponse, StatusResponse, RoleResponse
"""
import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


# =============================================================================
# ИНЦИДЕНТЫ
# =============================================================================

class IncidentBase(BaseModel):
    """Базовая схема инцидента (общие поля)."""
    title: str = Field(..., min_length=5, max_length=255)
    description: str = Field(..., min_length=10)
    category_id: uuid.UUID
    priority_id: uuid.UUID
    department_id: uuid.UUID
    initiator_id: uuid.UUID


class IncidentCreate(IncidentBase):
    """Создание инцидента."""
    pass


class IncidentUpdate(BaseModel):
    """Обновление инцидента (все поля опциональны)."""
    title: Optional[str] = Field(None, min_length=5, max_length=255)
    description: Optional[str] = Field(None, min_length=10)
    category_id: Optional[uuid.UUID] = None
    priority_id: Optional[uuid.UUID] = None
    department_id: Optional[uuid.UUID] = None


class IncidentResponse(BaseModel):
    """Ответ с данными инцидента."""
    id: uuid.UUID
    title: str
    description: str
    status_id: uuid.UUID
    priority_id: uuid.UUID
    department_id: uuid.UUID
    initiator_id: uuid.UUID
    executor_id: Optional[uuid.UUID]
    sla_deadline: datetime
    overdue: bool
    created_at: datetime
    
    class Config:
        from_attributes = True  # Разрешает ORM-режим (загрузка из SQLAlchemy моделей)


# =============================================================================
# ОПЕРАЦИИ С ИНЦИДЕНТАМИ
# =============================================================================

class StatusChange(BaseModel):
    """Смена статуса инцидента."""
    status_id: uuid.UUID
    user_id: Optional[uuid.UUID] = None  # Кто изменил (для истории)
    comment: Optional[str] = None  # Комментарий к изменению


class AssignExecutor(BaseModel):
    """Назначение исполнителя."""
    executor_id: uuid.UUID
    assigned_by_id: Optional[uuid.UUID] = None  # Кто назначил (для уведомлений)


class TakeIncident(BaseModel):
    """Взять инцидент в работу."""
    user_id: uuid.UUID  # Кто берёт в работу


class CloseIncident(BaseModel):
    """Закрытие инцидента."""
    user_id: uuid.UUID


class UpdateDeadline(BaseModel):
    """Изменение дедлайна инцидента."""
    new_deadline: datetime
    user_id: uuid.UUID  # Кто изменил
    reason: Optional[str] = None  # Причина изменения
    sla_violation_confirmed: bool = False  # Подтверждение нарушения SLA (для статистики)


# =============================================================================
# СПРАВОЧНИКИ
# =============================================================================

class CategoryResponse(BaseModel):
    """Ответ с данными категории."""
    id: uuid.UUID
    name: str
    description: Optional[str] = None
    is_active: bool = True
    
    class Config:
        from_attributes = True


class PriorityResponse(BaseModel):
    """Ответ с данными приоритета."""
    id: uuid.UUID
    name: str
    level: int
    color: str
    
    class Config:
        from_attributes = True


class StatusResponse(BaseModel):
    """Ответ с данными статуса."""
    id: uuid.UUID
    name: str
    color: str
    
    class Config:
        from_attributes = True


class RoleResponse(BaseModel):
    """Ответ с данными роли."""
    id: uuid.UUID
    name: str
    description: Optional[str] = None
    
    class Config:
        from_attributes = True
