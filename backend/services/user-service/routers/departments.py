"""
Department management routes
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from shared import get_db
from shared.models import Department, User, Incident
from schemas import DepartmentCreate, DepartmentUpdate, DepartmentResponse

router = APIRouter()


@router.get("")
async def list_departments(
    page: int = 1, limit: int = 20,
    db: AsyncSession = Depends(get_db)
):
    offset = (page - 1) * limit
    result = await db.execute(select(Department).offset(offset).limit(limit))
    departments = result.scalars().all()
    total = await db.execute(select(func.count()).select_from(Department))
    
    return {"data": departments, "total": total.scalar(), "page": page, "limit": limit}


@router.get("/{dept_id}", response_model=DepartmentResponse)
async def get_department(dept_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Department).where(Department.id == dept_id))
    dept = result.scalar_one_or_none()
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")
    return dept


@router.post("", response_model=DepartmentResponse, status_code=201)
async def create_department(data: DepartmentCreate, db: AsyncSession = Depends(get_db)):
    dept = Department(name=data.name, description=data.description, manager_id=data.manager_id)
    db.add(dept)
    await db.commit()
    await db.refresh(dept)
    return dept


@router.put("/{dept_id}", response_model=DepartmentResponse)
async def update_department(dept_id: str, data: DepartmentUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Department).where(Department.id == dept_id))
    dept = result.scalar_one_or_none()
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")
    
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(dept, field, value)
    
    await db.commit()
    await db.refresh(dept)
    return dept
