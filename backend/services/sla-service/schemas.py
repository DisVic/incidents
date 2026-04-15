import uuid
from typing import Optional
from pydantic import BaseModel


class SLAPolicyCreate(BaseModel):
    priority_id: uuid.UUID
    resolution_hours: int
    description: Optional[str] = None


class SLAPolicyResponse(BaseModel):
    id: uuid.UUID
    priority_id: uuid.UUID
    resolution_hours: int
    description: Optional[str]
    
    class Config:
        from_attributes = True


class EscalationRuleCreate(BaseModel):
    level: int
    notify_role_id: uuid.UUID
    condition_type: str


class EscalationRuleResponse(BaseModel):
    id: uuid.UUID
    level: int
    notify_role_id: uuid.UUID
    condition_type: str
    is_active: bool
    
    class Config:
        from_attributes = True
