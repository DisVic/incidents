"""
API SLA-политик: время на решение для каждого приоритета.

Endpoint'ы:
- GET /sla/policies — список всех SLA-политик
- POST /sla/policies — создать политику
- PUT /sla/policies/{id} — обновить политику
- DELETE /sla/policies/{id} — удалить политику
- POST /sla/calculate-deadline — расчёт дедлайна (тестирование)
"""
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from pydantic import BaseModel

from shared import get_db, calculate_sla_deadline
from shared.models import SLAPolicy, Priority
from schemas import SLAPolicyCreate, SLAPolicyResponse

router = APIRouter()


class SLAPolicyUpdate(BaseModel):
    """Обновление SLA-политики (все поля опциональны)."""
    resolution_hours: int = None
    description: str = None


@router.get("/policies")
async def list_policies(db: AsyncSession = Depends(get_db)):
    """Список SLA-политик с названиями приоритетов."""
    result = await db.execute(
        select(SLAPolicy)
        .options(selectinload(SLAPolicy.priority))
        .order_by(SLAPolicy.priority_id)
    )
    policies = result.scalars().all()
    return [
        {
            "id": str(p.id),
            "priority_id": str(p.priority_id),
            "priority_name": p.priority.name if p.priority else None,
            "resolution_hours": p.resolution_hours,
            "description": p.description
        }
        for p in policies
    ]


@router.post("/policies")
async def create_policy(data: SLAPolicyCreate, db: AsyncSession = Depends(get_db)):
    """
    Создание SLA-политики для приоритета.
    
    resolution_hours: время на решение в часах.
    """
    # Проверка: политика для этого приоритета уже существует
    result = await db.execute(
        select(SLAPolicy).where(SLAPolicy.priority_id == data.priority_id)
    )
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Политика для этого приоритета уже существует")
    
    policy = SLAPolicy(
        priority_id=data.priority_id,
        resolution_hours=data.resolution_hours,
        description=data.description
    )
    
    db.add(policy)
    await db.commit()
    await db.refresh(policy)
    return {"id": str(policy.id), "priority_id": str(policy.priority_id), "resolution_hours": policy.resolution_hours, "description": policy.description}


@router.put("/policies/{policy_id}")
async def update_policy(policy_id: str, data: SLAPolicyUpdate, db: AsyncSession = Depends(get_db)):
    """Обновление времени решения или описания SLA-политики."""
    result = await db.execute(
        select(SLAPolicy)
        .options(selectinload(SLAPolicy.priority))
        .where(SLAPolicy.id == policy_id)
    )
    policy = result.scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=404, detail="SLA-политика не найдена")
    
    if data.resolution_hours is not None:
        policy.resolution_hours = data.resolution_hours
    if data.description is not None:
        policy.description = data.description
    
    await db.commit()
    await db.refresh(policy)
    return {
        "id": str(policy.id),
        "priority_id": str(policy.priority_id),
        "priority_name": policy.priority.name if policy.priority else None,
        "resolution_hours": policy.resolution_hours,
        "description": policy.description
    }


@router.delete("/policies/{policy_id}")
async def delete_policy(policy_id: str, db: AsyncSession = Depends(get_db)):
    """Удаление SLA-политики."""
    result = await db.execute(select(SLAPolicy).where(SLAPolicy.id == policy_id))
    policy = result.scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=404, detail="SLA-политика не найдена")
    
    await db.delete(policy)
    await db.commit()
    return {"message": "SLA-политика удалена"}


@router.post("/calculate-deadline")
async def calculate_deadline(
    created_at: str,
    resolution_hours: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Рассчитывает дедлайн по времени создания и времени на решение.
    
    Args:
        created_at: Время создания инцидента (ISO 8601)
        resolution_hours: Время на решение в часах
    """
    from datetime import datetime
    created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    deadline = calculate_sla_deadline(created, resolution_hours)
    return {"deadline": deadline.isoformat()}
