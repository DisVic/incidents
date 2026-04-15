"""
Reference data routes (categories, priorities, statuses)
"""
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from shared import get_db
from shared.models import Category, Priority, Status, Role
from schemas import CategoryResponse, PriorityResponse, StatusResponse, RoleResponse
from typing import List

router = APIRouter()


# === CATEGORIES ===

class CategoryCreate(BaseModel):
    name: str
    description: str = None

class CategoryUpdate(BaseModel):
    name: str = None
    description: str = None
    is_active: bool = None


@router.get("/categories", response_model=List[CategoryResponse])
async def list_categories(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Category).order_by(Category.name))
    return result.scalars().all()


@router.post("/categories")
async def create_category(data: CategoryCreate, db: AsyncSession = Depends(get_db)):
    category = Category(name=data.name, description=data.description)
    db.add(category)
    await db.commit()
    await db.refresh(category)
    return {"id": str(category.id), "name": category.name, "description": category.description, "is_active": category.is_active}


@router.put("/categories/{category_id}")
async def update_category(category_id: str, data: CategoryUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Category).where(Category.id == category_id))
    category = result.scalar_one_or_none()
    if not category:
        raise HTTPException(status_code=404, detail="Категория не найдена")
    
    if data.name is not None:
        category.name = data.name
    if data.description is not None:
        category.description = data.description
    if data.is_active is not None:
        category.is_active = data.is_active
    
    await db.commit()
    return {"id": str(category.id), "name": category.name, "description": category.description, "is_active": category.is_active}


@router.delete("/categories/{category_id}")
async def delete_category(category_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Category).where(Category.id == category_id))
    category = result.scalar_one_or_none()
    if not category:
        raise HTTPException(status_code=404, detail="Категория не найдена")
    
    await db.delete(category)
    await db.commit()
    return {"message": "Категория удалена"}


# === PRIORITIES ===

class PriorityUpdate(BaseModel):
    name: str = None
    color: str = None


@router.get("/priorities", response_model=List[PriorityResponse])
async def list_priorities(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Priority).order_by(Priority.level.desc()))
    return result.scalars().all()


@router.put("/priorities/{priority_id}")
async def update_priority(priority_id: str, data: PriorityUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Priority).where(Priority.id == priority_id))
    priority = result.scalar_one_or_none()
    if not priority:
        raise HTTPException(status_code=404, detail="Приоритет не найден")
    
    if data.name is not None:
        priority.name = data.name
    if data.color is not None:
        priority.color = data.color
    
    await db.commit()
    return {"id": str(priority.id), "name": priority.name, "level": priority.level, "color": priority.color}


# === STATUSES ===

class StatusCreate(BaseModel):
    name: str
    color: str = "#6B7280"

class StatusUpdate(BaseModel):
    name: str = None
    color: str = None


@router.get("/statuses", response_model=List[StatusResponse])
async def list_statuses(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Status))
    return result.scalars().all()


@router.post("/statuses")
async def create_status(data: StatusCreate, db: AsyncSession = Depends(get_db)):
    status = Status(name=data.name, color=data.color)
    db.add(status)
    await db.commit()
    await db.refresh(status)
    return {"id": str(status.id), "name": status.name, "color": status.color}


@router.put("/statuses/{status_id}")
async def update_status(status_id: str, data: StatusUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Status).where(Status.id == status_id))
    status = result.scalar_one_or_none()
    if not status:
        raise HTTPException(status_code=404, detail="Статус не найден")
    
    if data.name is not None:
        status.name = data.name
    if data.color is not None:
        status.color = data.color
    
    await db.commit()
    return {"id": str(status.id), "name": status.name, "color": status.color}


@router.delete("/statuses/{status_id}")
async def delete_status(status_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Status).where(Status.id == status_id))
    status = result.scalar_one_or_none()
    if not status:
        raise HTTPException(status_code=404, detail="Статус не найден")
    
    await db.delete(status)
    await db.commit()
    return {"message": "Статус удалён"}


# === ROLES ===

@router.get("/roles", response_model=List[RoleResponse])
async def list_roles(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Role))
    return result.scalars().all()
