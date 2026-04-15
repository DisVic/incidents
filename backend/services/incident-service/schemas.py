"""
Pydantic schemas for Incident Service
"""
import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class IncidentBase(BaseModel):
    title: str = Field(..., min_length=5, max_length=255)
    description: str = Field(..., min_length=10)
    category_id: uuid.UUID
    priority_id: uuid.UUID
    department_id: uuid.UUID
    initiator_id: uuid.UUID


class IncidentCreate(IncidentBase):
    pass


class IncidentUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    category_id: Optional[uuid.UUID] = None
    priority_id: Optional[uuid.UUID] = None


class IncidentResponse(BaseModel):
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
        from_attributes = True


class StatusChange(BaseModel):
    status_id: uuid.UUID
    user_id: Optional[uuid.UUID] = None
    comment: Optional[str] = None


class AssignExecutor(BaseModel):
    executor_id: uuid.UUID
    assigned_by_id: Optional[uuid.UUID] = None  # Кто назначил (для уведомлений)


class TakeIncident(BaseModel):
    user_id: uuid.UUID  # Кто берёт в работу


class CloseIncident(BaseModel):
    user_id: uuid.UUID


class UpdateDeadline(BaseModel):
    new_deadline: datetime
    user_id: uuid.UUID  # Кто изменил
    reason: Optional[str] = None  # Причина изменения
    sla_violation_confirmed: bool = False  # Подтверждение что SLA был нарушен


# === Reference schemas ===

class CategoryResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str] = None
    is_active: bool = True
    
    class Config:
        from_attributes = True


class PriorityResponse(BaseModel):
    id: uuid.UUID
    name: str
    level: int
    color: str
    
    class Config:
        from_attributes = True


class StatusResponse(BaseModel):
    id: uuid.UUID
    name: str
    color: str
    
    class Config:
        from_attributes = True


class RoleResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str] = None
    
    class Config:
        from_attributes = True
