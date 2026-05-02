"""
API инцидентов — создание, назначение, изменение статуса, приоритета.

Endpoint'ы:
- GET /incidents — список с фильтрацией, сортировкой, пагинацией
- GET /incidents/{id} — данные инцидента
- PUT /incidents/{id} — редактирование инцидента:
    * Инициатор: может менять заголовок, описание, категорию, приоритет, отдел (если статус "Новый" и нет исполнителя)
    * Admin/Manager: могут менять приоритет и отдел (если статус не "Решён"/"Закрыт")
- POST /incidents — создание инцидента
- POST /incidents/{id}/take — взять в работу
- POST /incidents/{id}/assign — назначить исполнителя
- POST /incidents/{id}/resolve — отметить решённым
- POST /incidents/{id}/close — закрыть
- POST /incidents/{id}/status — изменить статус
- POST /incidents/{id}/priority — изменить приоритет
- PUT /incidents/{id}/deadline — изменить дедлайн
- GET /incidents/{id}/history — история изменений
"""
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from shared import get_db, calculate_sla_deadline
from shared.models import Incident, Status, Priority, Category, Department, User, SLAPolicy, IncidentHistory, Comment, Attachment, Notification
from shared.utils import get_sla_percentage, get_sla_remaining_time, get_sla_status_color
from shared.tasks import notify_incident_created, notify_priority_changed
from schemas import IncidentCreate, IncidentUpdate, IncidentResponse, StatusChange, CloseIncident, AssignExecutor, TakeIncident, UpdateDeadline

router = APIRouter()


async def get_status_by_name(db, name: str) -> Status:
    """Находит статус по названию (Новый, В работе, etc.)."""
    result = await db.execute(select(Status).where(Status.name == name))
    return result.scalar_one_or_none()


def incident_to_dict(incident: Incident) -> dict:
    """
    Конвертирует ORM-объект в словарь для JSON-ответа.
    Добавляет вычисляемые SLA-метрики: % использованного времени, остаток, цвет статуса.
    """
    # Считаем SLA-метрики
    sla_percentage = 0
    sla_remaining = None
    sla_status_color = "green"
    is_overdue = incident.overdue
    
    if incident.sla_deadline:
        sla_percentage = get_sla_percentage(
            incident.created_at, 
            incident.sla_deadline,
            incident.resolved_at,
            incident.closed_at
        )
        sla_remaining = get_sla_remaining_time(
            incident.sla_deadline,
            None,
            incident.resolved_at,
            incident.closed_at
        )
        # Динамически определяем просрочку: для активных — по текущему времени,
        # для закрытых/решённых — используем зафиксированное was_overdue
        if not incident.resolved_at and not incident.closed_at:
            is_overdue = datetime.utcnow() > incident.sla_deadline
        else:
            is_overdue = incident.was_overdue if incident.was_overdue is not None else incident.overdue
        sla_status_color = get_sla_status_color(sla_percentage, is_overdue)
    
    return {
        "id": str(incident.id),
        "title": incident.title,
        "description": incident.description,
        "status_id": str(incident.status_id),
        "status_name": incident.status.name if incident.status else None,
        "status_color": incident.status.color if incident.status else None,
        "priority_id": str(incident.priority_id),
        "priority_name": incident.priority.name if incident.priority else None,
        "priority_color": incident.priority.color if incident.priority else None,
        "category_id": str(incident.category_id) if incident.category_id else None,
        "category_name": incident.category.name if incident.category else None,
        "department_id": str(incident.department_id),
        "department_name": incident.department.name if incident.department else None,
        "initiator_id": str(incident.initiator_id),
        "initiator_name": incident.initiator.full_name if incident.initiator else None,
        "initiator_avatar": incident.initiator.avatar if incident.initiator else None,
        "executor_id": str(incident.executor_id) if incident.executor_id else None,
        "executor_name": incident.executor.full_name if incident.executor else None,
        "executor_avatar": incident.executor.avatar if incident.executor else None,
        "sla_deadline": incident.sla_deadline.isoformat() if incident.sla_deadline else None,
        "sla_percentage": round(sla_percentage, 1),
        "sla_remaining": sla_remaining,
        "sla_status_color": sla_status_color,
        "overdue": is_overdue if incident.sla_deadline else incident.overdue,
        "created_at": incident.created_at.isoformat() if incident.created_at else None,
        "assigned_at": incident.assigned_at.isoformat() if incident.assigned_at else None,
        "in_progress_at": incident.in_progress_at.isoformat() if incident.in_progress_at else None,
        "resolved_at": incident.resolved_at.isoformat() if incident.resolved_at else None,
        "closed_at": incident.closed_at.isoformat() if incident.closed_at else None,
    }


@router.get("")
async def list_incidents(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status_id: str = None,
    priority_id: str = None,
    department_id: str = None,
    executor_id: str = None,  # Фильтр по исполнителю
    no_executor: bool = None,  # Фильтр "без исполнителя"
    overdue: bool = None,
    sla_status: str = Query(None, regex="^(overdue|near|ok)$"),
    search: str = None,
    sort_field: str = Query("created_at", regex="^(created_at|sla_deadline|priority|title)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    user_department_id: str = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Список инцидентов с фильтрацией, сортировкой и пагинацией.
    
    Query params:
    - page, limit: пагинация
    - status_id, priority_id, department_id, executor_id: фильтры (UUID strings)
    - no_executor: только без исполнителя (True)
    - overdue: только просроченные (True/False)
    - sla_status: 'overdue' (просрочен), 'near' (>80% SLA), 'ok' (<80%)
    - search: поиск по заголовку
    - sort_field, sort_order: сортировка
    - user_department_id: фильтр по отделу (для Executor)
    """
    # Convert UUID strings to UUID objects
    import uuid as uuid_module
    status_uuid = uuid_module.UUID(status_id) if status_id else None
    priority_uuid = uuid_module.UUID(priority_id) if priority_id else None
    department_uuid = uuid_module.UUID(department_id) if department_id else None
    executor_uuid = uuid_module.UUID(executor_id) if executor_id else None
    user_dept_uuid = uuid_module.UUID(user_department_id) if user_department_id else None
    
    query = select(Incident).options(
        selectinload(Incident.status),
        selectinload(Incident.priority),
        selectinload(Incident.category),
        selectinload(Incident.department),
        selectinload(Incident.initiator),
        selectinload(Incident.executor)
    )
    
    if status_uuid:
        query = query.where(Incident.status_id == status_uuid)
    if priority_uuid:
        query = query.where(Incident.priority_id == priority_uuid)
    if department_uuid:
        query = query.where(Incident.department_id == department_uuid)
    if executor_uuid:
        query = query.where(Incident.executor_id == executor_uuid)
    if no_executor is not None and no_executor:
        query = query.where(Incident.executor_id.is_(None))
    if overdue is not None:
        query = query.where(Incident.overdue == overdue)
    
    # SLA status filter (more precise than just overdue boolean)
    if sla_status:
        from datetime import datetime
        # Get closed statuses to exclude from "near" filter
        closed_result = await db.execute(
            select(Status.id).where(Status.name.in_(["Решён", "Закрыт"]))
        )
        closed_ids = [row[0] for row in closed_result.fetchall()]
    
        if sla_status == "overdue":
            # Show only overdue incidents
            query = query.where(Incident.overdue == True)
        elif sla_status == "near":
            # Near deadline: active incidents with 80%+ SLA used, excluding closed
            if closed_ids:
                query = query.where(Incident.status_id.notin_(closed_ids))
            query = query.where(Incident.overdue == False)
            # Will filter by percentage after fetching
        elif sla_status == "ok":
            # On time: not overdue and not near deadline
            query = query.where(Incident.overdue == False)
    
    # Filter by user department (for Executors - they can only see their department's incidents)
    if user_dept_uuid:
        query = query.where(Incident.department_id == user_dept_uuid)
    
    # Search by title
    if search:
        query = query.where(Incident.title.ilike(f"%{search}%"))
    
    # For sla_status "near" and "ok", we need to filter by percentage after fetching
    # So we get more data and filter in Python
    if sla_status in ["near", "ok"]:
        # Get all matching incidents first (no pagination)
        result = await db.execute(query)
        all_incidents = result.scalars().all()
        
        # Filter by SLA percentage
        from datetime import datetime as dt
        now = dt.utcnow()
        filtered_incidents = []
        
        for incident in all_incidents:
            if incident.sla_deadline:
                total_time = (incident.sla_deadline - incident.created_at).total_seconds()
                # Use resolved_at or closed_at if available, otherwise use current time
                if incident.closed_at:
                    elapsed = (incident.closed_at - incident.created_at).total_seconds()
                elif incident.resolved_at:
                    elapsed = (incident.resolved_at - incident.created_at).total_seconds()
                else:
                    elapsed = (now - incident.created_at).total_seconds()
                if total_time > 0:
                    percentage = (elapsed / total_time) * 100
                    
                    if sla_status == "near" and percentage >= 80:
                        filtered_incidents.append(incident)
                    elif sla_status == "ok" and percentage < 80:
                        filtered_incidents.append(incident)
            elif sla_status == "ok":
                # No deadline = ok
                filtered_incidents.append(incident)
        
        # Sort filtered results
        def sort_key(inc):
            if sort_field == "priority":
                return inc.priority.level if inc.priority else 0
            elif sort_field == "title":
                return inc.title or ""
            elif sort_field == "sla_deadline":
                return inc.sla_deadline or dt.max
            else:
                return inc.created_at or dt.min
        
        reverse = sort_order == "desc"
        filtered_incidents.sort(key=sort_key, reverse=reverse)
        
        # Paginate
        total_count = len(filtered_incidents)
        offset = (page - 1) * limit
        paginated = filtered_incidents[offset:offset + limit]
        
        return {
            "data": [incident_to_dict(i) for i in paginated],
            "total": total_count,
            "page": page,
            "limit": limit
        }
    
    total = await db.execute(select(func.count()).select_from(query.subquery()))
    
    # Sorting
    order_func = lambda x: x.asc() if sort_order == "asc" else x.desc()
    
    if sort_field == "priority":
        # Join with Priority table for sorting by priority level
        query = query.join(Priority, Incident.priority_id == Priority.id)
        query = query.order_by(order_func(Priority.level))
    elif sort_field == "title":
        query = query.order_by(order_func(Incident.title))
    elif sort_field == "sla_deadline":
        query = query.order_by(order_func(Incident.sla_deadline))
    else:  # created_at (default)
        query = query.order_by(order_func(Incident.created_at))
    
    offset = (page - 1) * limit
    query = query.offset(offset).limit(limit)
    
    result = await db.execute(query)
    incidents = result.scalars().all()
    
    return {"data": [incident_to_dict(i) for i in incidents], "total": total.scalar(), "page": page, "limit": limit}


@router.get("/{incident_id}")
async def get_incident(incident_id: str, db: AsyncSession = Depends(get_db)):
    """Получение одного инцидента по ID с полными данными (статус, приоритет, исполнитель, SLA)."""
    result = await db.execute(
        select(Incident)
        .options(
            selectinload(Incident.status),
            selectinload(Incident.priority),
            selectinload(Incident.category),
            selectinload(Incident.department),
            selectinload(Incident.initiator),
            selectinload(Incident.executor)
        )
        .where(Incident.id == incident_id)
    )
    incident = result.scalar_one_or_none()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident_to_dict(incident)
    

@router.put("/{incident_id}")
async def update_incident(
    incident_id: str, 
    data: IncidentUpdate, 
    user_id: str = Query(...),
    user_role: str = Query(None),  # Роль пользователя (Admin/Manager)
    db: AsyncSession = Depends(get_db)
):
    """
    Редактирование инцидента.
    
    Права доступа:
    - Инициатор: может менять заголовок, описание, категорию, приоритет, отдел (если статус "Новый" и нет исполнителя)
    - Admin/Manager: могут менять отдел (если статус не "Решён"/"Закрыт")
    
    Ограничения:
    - Нельзя редактировать закрытые/решённые инциденты
    """
    # Получаем инцидент
    result = await db.execute(
        select(Incident)
        .options(
            selectinload(Incident.status),
            selectinload(Incident.priority),
            selectinload(Incident.category),
            selectinload(Incident.department)
        )
        .where(Incident.id == incident_id)
    )
    incident = result.scalar_one_or_none()
    
    if not incident:
        raise HTTPException(status_code=404, detail="Инцидент не найден")
    
    # Проверяем статус - нельзя редактировать решённые/закрытые
    if incident.status.name in ["Решён", "Закрыт"]:
        raise HTTPException(
            status_code=400,
            detail=f"Нельзя редактировать инцидент в статусе '{incident.status.name}'"
        )
    
    # Определяем права доступа
    is_initiator = str(incident.initiator_id) == user_id
    is_admin = user_role in ["Admin", "admin", "Admin"]
    is_manager = user_role in ["Manager", "manager"]
    
    # Проверка прав
    if not is_initiator and not is_admin and not is_manager:
        raise HTTPException(
            status_code=403,
            detail=f"Нет прав на редактирование. Вы: {user_role or 'гость'}, инициатор: {is_initiator}"
        )
    
    # Инициатор может редактировать только если статус "Новый" и нет исполнителя
    if is_initiator and not is_admin and not is_manager:
        if incident.status.name != "Новый":
            raise HTTPException(
                status_code=400,
                detail="Инициатор может редактировать инцидент только в статусе 'Новый'"
            )
        if incident.executor_id:
            raise HTTPException(
                status_code=400,
                detail="Инициатор не может редактировать инцидент, у которого уже есть исполнитель"
            )
    
    # Admin/Manager могут менять отдел при любом статусе (кроме Решён/Закрыт)
    # Инициатор может менять отдел только если статус "Новый"
    can_change_department = is_admin or is_manager or (is_initiator and incident.status.name == "Новый")
    
    # Собираем изменения для истории
    changes = []
    old_department_name = incident.department.name if incident.department else "—"
    
    # Обновляем поля - ТОЛЬКО если есть права
    # Инициатор может менять всё, Admin/Manager - только отдел
    if is_initiator and not is_admin and not is_manager:
        # Инициатор может менять заголовок, описание, категорию, приоритет
        if data.title is not None and data.title != incident.title:
            changes.append(f"Заголовок: {incident.title} → {data.title}")
            incident.title = data.title
        
        if data.description is not None and data.description != incident.description:
            changes.append("Описание обновлено")
            incident.description = data.description
        
        if data.category_id is not None and data.category_id != incident.category_id:
            # Получаем новую категорию
            cat_result = await db.execute(select(Category).where(Category.id == data.category_id))
            new_cat = cat_result.scalar_one_or_none()
            if new_cat:
                old_cat_name = incident.category.name if incident.category else "—"
                changes.append(f"Категория: {old_cat_name} → {new_cat.name}")
                incident.category_id = data.category_id
        
        if data.priority_id is not None and data.priority_id != incident.priority_id:
            # Получаем новый приоритет и пересчитываем SLA
            pri_result = await db.execute(select(Priority).where(Priority.id == data.priority_id))
            new_priority = pri_result.scalar_one_or_none()
            if new_priority:
                old_priority_name = incident.priority.name if incident.priority else "—"
                changes.append(f"Приоритет: {old_priority_name} → {new_priority.name}")
                
                # Пересчитываем SLA-дедлайн
                sla_result = await db.execute(select(SLAPolicy).where(SLAPolicy.priority_id == data.priority_id))
                sla_policy = sla_result.scalar_one_or_none()
                
                if sla_policy:
                    old_deadline = incident.sla_deadline
                    incident.sla_deadline = calculate_sla_deadline(incident.created_at, sla_policy.resolution_hours)
                    incident.priority_id = data.priority_id
                    
                    # Сбрасываем overdue, если новый дедлайн в будущем
                    if incident.sla_deadline > datetime.utcnow():
                        incident.overdue = False
                    
                    changes.append(f"Дедлайн: {old_deadline.strftime('%d.%m.%Y %H:%M')} → {incident.sla_deadline.strftime('%d.%m.%Y %H:%M')}")
                else:
                    incident.priority_id = data.priority_id
    else:
        # Admin/Manager могут менять ТОЛЬКО отдел
        pass  # priority_id и другие поля игнорируем
    
    if data.department_id is not None and data.department_id != incident.department_id:
        if not can_change_department:
            raise HTTPException(
                status_code=403,
                detail="Отдел можно изменить только если статус 'Новый' или вы Admin/Manager"
            )
    
        # Получаем новый отдел
        dept_result = await db.execute(select(Department).where(Department.id == data.department_id))
        new_dept = dept_result.scalar_one_or_none()
        if new_dept:
            changes.append(f"Отдел: {old_department_name} → {new_dept.name}")
            incident.department_id = data.department_id
            
            # Если исполнитель из другого отдела - сбрасываем назначение
            if incident.executor_id:
                exec_result = await db.execute(select(User).where(User.id == incident.executor_id))
                executor = exec_result.scalar_one_or_none()
                if executor and str(executor.department_id) != data.department_id:
                    # Сбрасываем исполнителя
                    old_executor_name = executor.full_name
                    incident.executor_id = None
                    incident.assigned_at = None
                    
                    # Если статус был "Назначен" или "В работе", возвращаем в "Новый"
                    if incident.status.name in ["Назначен", "В работе"]:
                        new_status = await get_status_by_name(db, "Новый")
                        if new_status:
                            incident.status_id = new_status.id
                            changes.append(f"Исполнитель сброшен: {old_executor_name} (из другого отдела)")
                            changes.append(f"Статус: {incident.status.name} → Новый")
    
    # Если не было изменений
    if not changes:
        raise HTTPException(status_code=400, detail="Нет изменений для применения")
    
    # Добавляем запись в историю
    history = IncidentHistory(
        incident_id=incident.id,
        user_id=uuid.UUID(user_id),
        previous_status_id=incident.status_id,
        new_status_id=incident.status_id,
        comment="Инцидент отредактирован: " + "; ".join(changes)
    )
    db.add(history)
    
    await db.commit()
    await db.refresh(incident)
    
    # Перезагружаем с данными
    result = await db.execute(
        select(Incident)
        .options(
            selectinload(Incident.status),
            selectinload(Incident.priority),
            selectinload(Incident.category),
            selectinload(Incident.department),
            selectinload(Incident.initiator),
            selectinload(Incident.executor)
        )
        .where(Incident.id == incident.id)
    )
    incident = result.scalar_one()
    
    return incident_to_dict(incident)
    

@router.post("", status_code=201)
async def create_incident(data: IncidentCreate, db: AsyncSession = Depends(get_db)):
    """
    Создание инцидента.
    
    - Устанавливает статус "Новый"
    - Рассчитывает SLA-дедлайн по приоритету
    - Добавляет запись в историю
    - Отправляет уведомления (Manager, Admin, Executor'ы отдела)
    """
    new_status = await get_status_by_name(db, "Новый")
    if not new_status:
        raise HTTPException(status_code=500, detail="Default status not found")
    
    sla_result = await db.execute(
        select(SLAPolicy).where(SLAPolicy.priority_id == data.priority_id)
    )
    sla_policy = sla_result.scalar_one_or_none()
    
    created_at = datetime.utcnow()
    sla_deadline = calculate_sla_deadline(
        created_at,
        sla_policy.resolution_hours if sla_policy else 24
    )
    
    incident = Incident(
        title=data.title,
        description=data.description,
        category_id=data.category_id,
        priority_id=data.priority_id,
        status_id=new_status.id,
        department_id=data.department_id,
        initiator_id=data.initiator_id,
        sla_deadline=sla_deadline
    )
    
    db.add(incident)
    await db.flush()
    
    history = IncidentHistory(
        incident_id=incident.id,
        user_id=data.initiator_id,
        new_status_id=new_status.id,
        comment="Инцидент создан"
    )
    db.add(history)
    
    await db.commit()
    await db.refresh(incident)
    
    # Send notification about new incident
    notify_incident_created.delay(str(incident.id))
    
    # Reload with related data
    result = await db.execute(
        select(Incident)
        .options(
            selectinload(Incident.status),
            selectinload(Incident.priority),
            selectinload(Incident.category),
            selectinload(Incident.department),
            selectinload(Incident.initiator),
            selectinload(Incident.executor)
        )
        .where(Incident.id == incident.id)
    )
    incident = result.scalar_one()
    return incident_to_dict(incident)


@router.post("/{incident_id}/take")
async def take_incident(incident_id: str, data: TakeIncident, db: AsyncSession = Depends(get_db)):
    """
    Взять инцидент в работу.
    
    Executor берёт инцидент только своего отдела.
    Статус меняется на "В работе".
    """
    # Получаем инцидент
    result = await db.execute(
        select(Incident)
        .options(selectinload(Incident.status))
        .where(Incident.id == incident_id)
    )
    incident = result.scalar_one_or_none()
    
    if not incident:
        raise HTTPException(status_code=404, detail="Инцидент не найден")
    
    # Проверяем, что инцидент не закрыт
    if incident.status.name == "Закрыт":
        raise HTTPException(status_code=400, detail="Нельзя взять в работу закрытый инцидент")
    
    if incident.status.name == "Решён":
        raise HTTPException(status_code=400, detail="Нельзя взять в работу решённый инцидент")
    
    if incident.executor_id:
        raise HTTPException(status_code=400, detail="У инцидента уже есть исполнитель. Сначала сбросьте назначение.")
    
    if incident.status.name not in ["Новый", "Назначен"]:
        raise HTTPException(
            status_code=400,
            detail=f"Нельзя взять в работу инцидент в статусе '{incident.status.name}'"
        )
    
    # Получаем пользователя
    user_result = await db.execute(
        select(User).options(selectinload(User.role)).where(User.id == data.user_id)
    )
    user = user_result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Пользователь заблокирован")
    
    # Проверяем роль
    if user.role.name not in ["Executor", "Manager", "Admin"]:
        raise HTTPException(
            status_code=400,
            detail=f"Пользователь с ролью '{user.role.name}' не может брать инциденты в работу"
        )
    
    # Executor может брать только инциденты своего отдела
    # Manager и Admin могут брать любые инциденты
    if user.role.name == "Executor" and user.department_id:
        if incident.department_id != user.department_id:
            # Получаем название отдела инцидента для сообщения
            dept_result = await db.execute(
                select(Department).where(Department.id == incident.department_id)
            )
            incident_dept = dept_result.scalar_one_or_none()
            dept_name = incident_dept.name if incident_dept else "неизвестный отдел"
            raise HTTPException(
                status_code=403,
                detail=f"Вы можете брать инциденты только своего отдела. Этот инцидент относится к отделу '{dept_name}'"
            )
    
    in_progress = await get_status_by_name(db, "В работе")
    
    old_status = incident.status_id
    incident.executor_id = data.user_id
    incident.status_id = in_progress.id
    incident.in_progress_at = datetime.utcnow()
    
    history = IncidentHistory(
        incident_id=incident.id,
        user_id=data.user_id,
        previous_status_id=old_status,
        new_status_id=in_progress.id,
        comment="Взят в работу"
    )
    db.add(history)
    
    await db.commit()
    
    # Send notification about assignment (user assigned themselves)
    from shared.tasks import notify_incident_assigned
    notify_incident_assigned.delay(str(incident.id), str(data.user_id), str(data.user_id))
    
    return {"message": "Инцидент взят в работу"}


@router.post("/{incident_id}/assign")
async def assign_incident(incident_id: str, data: AssignExecutor, 
                          db: AsyncSession = Depends(get_db)):
    """
    Назначить исполнителя на инцидент.
    
    - Manager/Admin назначает (Executor не может переназначить)
    - Статус -> "Назначен" (если был "Новый")
    - Executor назначается только на инциденты своего отдела
    """
    # Получаем инцидент
    result = await db.execute(
        select(Incident)
        .options(selectinload(Incident.status), selectinload(Incident.department))
        .where(Incident.id == incident_id)
    )
    incident = result.scalar_one_or_none()
    
    if not incident:
        raise HTTPException(status_code=404, detail="Инцидент не найден")
    
    # Проверяем статус
    if incident.status.name == "Закрыт":
        raise HTTPException(status_code=400, detail="Нельзя назначить исполнителя на закрытый инцидент")
    
    if incident.status.name == "Решён":
        raise HTTPException(status_code=400, detail="Нельзя назначить исполнителя на решённый инцидент")
    
    # Получаем того, кто назначает
    assigned_by = None
    if data.assigned_by_id:
        assigned_by_result = await db.execute(
            select(User).options(selectinload(User.role), selectinload(User.department))
            .where(User.id == data.assigned_by_id)
        )
        assigned_by = assigned_by_result.scalar_one_or_none()
    
    # Переназначение разрешено только для Admin/Manager
    # Executor не может переназначить инцидент, который уже в работе
    is_reassignment = incident.executor_id is not None
    if is_reassignment and assigned_by and assigned_by.role.name == "Executor":
        raise HTTPException(
            status_code=403,
            detail="Исполнитель не может переназначить инцидент. Обратитесь к менеджеру или администратору."
        )
    
    # Получаем исполнителя
    executor_result = await db.execute(
        select(User).options(selectinload(User.role), selectinload(User.department)).where(User.id == data.executor_id)
    )
    executor = executor_result.scalar_one_or_none()
    
    if not executor:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    if not executor.is_active:
        raise HTTPException(status_code=400, detail="Пользователь заблокирован")
    
    # Проверяем роль (Executor, Manager или Admin могут быть исполнителями)
    if executor.role.name not in ["Executor", "Manager", "Admin"]:
        raise HTTPException(
            status_code=400, 
            detail=f"Пользователь с ролью '{executor.role.name}' не может быть исполнителем. Требуется роль Executor, Manager или Admin."
        )
    
    # Executor может быть назначен только на инцидент своего отдела
    if executor.role.name == "Executor" and executor.department_id:
        if incident.department_id != executor.department_id:
            raise HTTPException(
                status_code=400,
                detail=f"Нельзя назначить исполнителя из другого отдела. Инцидент относится к отделу '{incident.department.name if incident.department else 'неизвестно'}', а исполнитель — к '{executor.department.name if executor.department else 'без отдела'}'"
            )
    
    # Manager может назначать только на инциденты своего отдела и исполнителей из этого отдела
    # Admin может назначать любого
    if assigned_by and assigned_by.role.name == "Manager":
        # Проверяем что инцидент из отдела менеджера
        if assigned_by.department_id and incident.department_id != assigned_by.department_id:
            raise HTTPException(
                status_code=403,
                detail=f"Менеджер может работать только с инцидентами своего отдела. Инцидент относится к отделу '{incident.department.name if incident.department else 'неизвестно'}', а вы — к '{assigned_by.department.name if assigned_by.department else 'без отдела'}'"
            )
        # Проверяем что исполнитель из отдела инцидента (кроме Admin - они глобальные)
        if executor.role.name != "Admin" and executor.department_id != incident.department_id:
            raise HTTPException(
                status_code=403,
                detail=f"Менеджер может назначать только исполнителей из отдела инцидента. Исполнитель относится к отделу '{executor.department.name if executor.department else 'без отдела'}', а инцидент — к '{incident.department.name if incident.department else 'неизвестно'}'"
            )
    
    assigned_status = await get_status_by_name(db, "Назначен")
    
    old_status = incident.status_id
    old_executor_id = incident.executor_id
    incident.executor_id = data.executor_id
    
    # При первичном назначении меняем статус на "Назначен"
    if incident.status.name == "Новый":
        incident.status_id = assigned_status.id
        incident.assigned_at = datetime.utcnow()
    
    # История: различаем первичное назначение и переназначение
    if old_executor_id:
        comment = f"Исполнитель переназначен: {executor.full_name}"
    else:
        comment = f"Назначен исполнитель: {executor.full_name}"
    
    history = IncidentHistory(
        incident_id=incident.id,
        user_id=data.executor_id,
        previous_status_id=old_status,
        new_status_id=incident.status_id,
        comment=comment
    )
    db.add(history)
    
    await db.commit()
    
    # Send notification about assignment
    from shared.tasks import notify_incident_assigned
    assigned_by_id = data.assigned_by_id or data.executor_id  # Fallback to executor if not specified
    notify_incident_assigned.delay(str(incident.id), str(data.executor_id), str(assigned_by_id))
    
    return {"message": "Исполнитель назначен"}


@router.post("/{incident_id}/resolve")
async def resolve_incident(incident_id: str, executor_id: str, comment: str,
                           db: AsyncSession = Depends(get_db)):
    """
    Отметить инцидент как решённый.
    
    - Статус -> "Решён"
    - Фиксируется was_overdue для статистики
    - Отправляется уведомление
    """
    result = await db.execute(
        select(Incident)
        .options(selectinload(Incident.status))
        .where(Incident.id == incident_id)
    )
    incident = result.scalar_one_or_none()
    
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    
    resolved = await get_status_by_name(db, "Решён")
    
    old_status = incident.status_id
    old_status_name = incident.status.name if incident.status else None
    incident.status_id = resolved.id
    incident.resolved_at = datetime.utcnow()
    
    # Determine if incident was overdue at resolution time
    # Check explicitly against deadline, not just relying on overdue flag
    if incident.sla_deadline:
        incident.overdue = incident.resolved_at > incident.sla_deadline
    else:
        incident.overdue = False
    
    # Freeze overdue state for statistics (was_overdue never changes after this)
    incident.was_overdue = incident.overdue
    
    history = IncidentHistory(
        incident_id=incident.id,
        user_id=uuid.UUID(executor_id),
        previous_status_id=old_status,
        new_status_id=resolved.id,
        comment=f"Решён: {comment}"
    )
    db.add(history)
    
    await db.commit()
    
    # Send notification about resolved incident
    from shared.tasks import notify_incident_resolved
    notify_incident_resolved.delay(str(incident.id), executor_id, comment)
    
    return {"message": "Incident resolved"}


@router.post("/{incident_id}/close")
async def close_incident(incident_id: str, data: CloseIncident, db: AsyncSession = Depends(get_db)):
    """
    Закрыть инцидент.
    
    - Требует статус "Решён"
    - Статус -> "Закрыт"
    - Фиксируется was_overdue для статистики
    """
    result = await db.execute(
        select(Incident)
        .options(selectinload(Incident.status))
        .where(Incident.id == incident_id)
    )
    incident = result.scalar_one_or_none()
    
    if not incident:
        raise HTTPException(status_code=404, detail="Инцидент не найден")
    
    # Проверяем, что инцидент в статусе "Решён"
    if incident.status.name != "Решён":
        raise HTTPException(
            status_code=400, 
            detail=f"Нельзя закрыть инцидент в статусе '{incident.status.name}'. Сначала переведите в статус 'Решён'."
        )
    
    closed = await get_status_by_name(db, "Закрыт")
    
    old_status = incident.status_id
    incident.status_id = closed.id
    incident.closed_at = datetime.utcnow()
    
    # Determine if incident was overdue at close time
    # Check explicitly against deadline
    if incident.sla_deadline:
        incident.overdue = incident.closed_at > incident.sla_deadline
    else:
        incident.overdue = False
    
    # Freeze overdue state for statistics (was_overdue never changes after this)
    incident.was_overdue = incident.overdue
    
    history = IncidentHistory(
        incident_id=incident.id,
        user_id=data.user_id,
        previous_status_id=old_status,
        new_status_id=closed.id,
        comment="Инцидент закрыт"
    )
    db.add(history)
    
    await db.commit()
    
    # Send notification about closed incident
    from shared.tasks import notify_incident_closed
    notify_incident_closed.delay(str(incident.id), str(data.user_id))
    
    return {"message": "Incident closed"}


@router.post("/{incident_id}/status")
async def change_status(incident_id: str, data: StatusChange, db: AsyncSession = Depends(get_db)):
    """
    Изменить статус инцидента вручную.
    
    - Обновляет соответствующий timestamp (in_progress_at, resolved_at, closed_at)
    - Отправляет уведомление о смене статуса
    """
    result = await db.execute(
        select(Incident)
        .options(selectinload(Incident.status))
        .where(Incident.id == incident_id)
    )
    incident = result.scalar_one_or_none()
    
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    
    # Get new status
    new_status_result = await db.execute(select(Status).where(Status.id == data.status_id))
    new_status = new_status_result.scalar_one_or_none()
    
    if not new_status:
        raise HTTPException(status_code=404, detail="Status not found")
    
    # Check: cannot set "Назначен" status without executor
    if new_status.name == "Назначен" and not incident.executor_id:
        raise HTTPException(
            status_code=400, 
            detail="Нельзя установить статус 'Назначен' без исполнителя. Сначала назначьте исполнителя."
        )
    
    old_status_id = incident.status_id
    old_status_name = incident.status.name if incident.status else None
    
    # Update timestamps based on status
    now = datetime.utcnow()
    if new_status.name == "В работе" and not incident.in_progress_at:
        incident.in_progress_at = now
    elif new_status.name == "Решён" and not incident.resolved_at:
        incident.resolved_at = now
        # SLA stops when resolved - check if resolved before deadline
        if incident.sla_deadline and now <= incident.sla_deadline:
            incident.overdue = False
        # Freeze overdue state for statistics
        incident.was_overdue = incident.overdue
    elif new_status.name == "Закрыт" and not incident.closed_at:
        incident.closed_at = now
        # SLA stops when closed - check if closed before deadline
        if incident.sla_deadline and now <= incident.sla_deadline:
            incident.overdue = False
        # Freeze overdue state for statistics
        incident.was_overdue = incident.overdue
    
    incident.status_id = data.status_id
    
    # Add history entry
    history = IncidentHistory(
        incident_id=incident.id,
        user_id=data.user_id,
        previous_status_id=old_status_id,
        new_status_id=data.status_id,
        comment=data.comment or f"Статус изменён: {old_status_name} → {new_status.name}"
    )
    db.add(history)
    
    await db.commit()
    
    # Send notification about status change (excluding the one who changed it)
    from shared.tasks import notify_status_changed
    notify_status_changed.delay(
        str(incident.id), 
        old_status_name, 
        new_status.name, 
        data.comment or "",
        str(data.user_id) if data.user_id else None
    )
    
    return {"message": "Status changed"}


@router.get("/{incident_id}/history")
async def get_history(incident_id: str, db: AsyncSession = Depends(get_db)):
    """История изменений инцидента (таймлайн) — кто, когда, что изменил."""
    result = await db.execute(
        select(IncidentHistory)
        .where(IncidentHistory.incident_id == incident_id)
        .order_by(IncidentHistory.created_at.desc())
    )
    history = result.scalars().all()
    
    # Get status names
    status_ids = set()
    user_ids = set()
    for h in history:
        if h.previous_status_id:
            status_ids.add(h.previous_status_id)
        if h.new_status_id:
            status_ids.add(h.new_status_id)
        if h.user_id:
            user_ids.add(h.user_id)
    
    status_names = {}
    if status_ids:
        status_result = await db.execute(select(Status).where(Status.id.in_(status_ids)))
        for s in status_result.scalars().all():
            status_names[str(s.id)] = s.name
    
    user_names = {}
    if user_ids:
        user_result = await db.execute(select(User).where(User.id.in_(user_ids)))
        for u in user_result.scalars().all():
            user_names[str(u.id)] = u.full_name
    
    return [
        {
            "id": str(h.id),
            "incident_id": str(h.incident_id),
            "user_id": str(h.user_id) if h.user_id else None,
            "user_name": user_names.get(str(h.user_id)) if h.user_id else None,
            "previous_status_id": str(h.previous_status_id) if h.previous_status_id else None,
            "previous_status_name": status_names.get(str(h.previous_status_id)) if h.previous_status_id else None,
            "new_status_id": str(h.new_status_id) if h.new_status_id else None,
            "new_status_name": status_names.get(str(h.new_status_id)) if h.new_status_id else None,
            "comment": h.comment,
            "created_at": h.created_at.isoformat() if h.created_at else None,
        }
        for h in history
    ]


@router.post("/{incident_id}/priority")
async def change_priority(
    incident_id: str, 
    priority_id: str, 
    user_id: str = None,
    recalculate_deadline: bool = True,
    db: AsyncSession = Depends(get_db)
):
    """
    Изменить приоритет инцидента.
    
    - При повышении приоритета пересчитывает SLA-дедлайн
    - Отправляет уведомление об изменении
    """
    result = await db.execute(
        select(Incident)
        .options(
            selectinload(Incident.priority),
            selectinload(Incident.status)
        )
        .where(Incident.id == incident_id)
    )
    incident = result.scalar_one_or_none()
    
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    
    # Get new priority
    new_priority_result = await db.execute(
        select(Priority).where(Priority.id == priority_id)
    )
    new_priority = new_priority_result.scalar_one_or_none()
    
    if not new_priority:
        raise HTTPException(status_code=404, detail="Priority not found")
    
    old_priority_name = incident.priority.name if incident.priority else "N/A"
    old_deadline = incident.sla_deadline
    
    # Update priority
    incident.priority_id = priority_id
    
    # Recalculate deadline if requested
    new_deadline = None
    if recalculate_deadline:
        # Get SLA policy for new priority
        sla_result = await db.execute(
            select(SLAPolicy).where(SLAPolicy.priority_id == priority_id)
        )
        sla_policy = sla_result.scalar_one_or_none()
        
        if sla_policy:
            new_deadline = calculate_sla_deadline(
                incident.created_at,
                sla_policy.resolution_hours
            )
            incident.sla_deadline = new_deadline
            # Reset overdue flag if deadline is in the future
            if new_deadline > datetime.utcnow():
                incident.overdue = False
    
    # Add history entry
    comment = f"Приоритет изменён: {old_priority_name} → {new_priority.name}"
    if new_deadline:
        comment += f". Дедлайн пересчитан: {old_deadline.strftime('%d.%m.%Y %H:%M') if old_deadline else 'N/A'} → {new_deadline.strftime('%d.%m.%Y %H:%M')}"
    
    history = IncidentHistory(
        incident_id=incident.id,
        user_id=uuid.UUID(user_id) if user_id else None,
        previous_status_id=incident.status_id,
        new_status_id=incident.status_id,
        comment=comment
    )
    db.add(history)
    
    await db.commit()
    
    # Send notification about priority change
    notify_priority_changed.delay(
        str(incident.id),
        old_priority_name,
        new_priority.name,
        new_deadline.isoformat() if new_deadline else None,
        user_id
    )
    
    return {
        "message": "Priority changed",
        "old_priority": old_priority_name,
        "new_priority": new_priority.name,
        "old_deadline": old_deadline.isoformat() if old_deadline else None,
        "new_deadline": new_deadline.isoformat() if new_deadline else None,
        "deadline_recalculated": new_deadline is not None
    }


@router.put("/{incident_id}/deadline")
async def update_deadline(incident_id: str, data: UpdateDeadline, db: AsyncSession = Depends(get_db)):
    """
    Изменить SLA-дедлайн вручную (только Manager/Admin).
    
    - Manager может менять только для инцидентов своего отдела
    - Нельзя менять для закрытых/решённых
    - Опция sla_violation_confirmed для подтверждения нарушения SLA
    """
    from shared.models import Role
    
    # Get incident
    result = await db.execute(
        select(Incident)
        .options(selectinload(Incident.status))
        .where(Incident.id == incident_id)
    )
    incident = result.scalar_one_or_none()
    
    if not incident:
        raise HTTPException(status_code=404, detail="Инцидент не найден")
    
    # Get user who is changing deadline
    user_result = await db.execute(
        select(User).options(selectinload(User.role)).where(User.id == data.user_id)
    )
    user = user_result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    # Check permissions - only Manager and Admin can change deadline
    if user.role.name not in ["Manager", "Admin"]:
        raise HTTPException(
            status_code=403,
            detail="Только менеджер или администратор может изменить дедлайн"
        )
    
    # Manager can only change deadline for incidents in their department
    if user.role.name == "Manager" and user.department_id:
        if incident.department_id != user.department_id:
            raise HTTPException(
                status_code=403,
                detail="Менеджер может изменять дедлайн только для инцидентов своего отдела"
            )
    
    # Cannot change deadline for closed/resolved incidents
    if incident.status.name in ["Закрыт", "Решён"]:
        raise HTTPException(
            status_code=400,
            detail="Нельзя изменить дедлайн для закрытого или решённого инцидента"
        )
    
    old_deadline = incident.sla_deadline
    was_overdue_before = incident.overdue  # Запоминаем текущее состояние
    
    # Remove timezone info before saving to DB (column is TIMESTAMP WITHOUT TIME ZONE)
    new_deadline_naive = data.new_deadline.replace(tzinfo=None) if data.new_deadline.tzinfo else data.new_deadline
    incident.sla_deadline = new_deadline_naive
    
    # Update overdue flag based on new deadline
    now = datetime.utcnow()
    if new_deadline_naive > now:
        incident.overdue = False
    else:
        incident.overdue = True
    
    # Handle was_overdue based on sla_violation_confirmed flag
    # Manager can confirm SLA violation even if deadline was already extended
    if data.sla_violation_confirmed:
        # SLA violation confirmed - will be counted in statistics
        incident.was_overdue = True
    elif was_overdue_before:
        # Was overdue but manager says it's not critical
        incident.was_overdue = False
    # else: keep current was_overdue value (unchanged)
    
    # Add history entry
    comment = f"Дедлайн изменён: {old_deadline.strftime('%d.%m.%Y %H:%M') if old_deadline else 'N/A'} → {new_deadline_naive.strftime('%d.%m.%Y %H:%M')}"
    if data.reason:
        comment += f". Причина: {data.reason}"
    if data.sla_violation_confirmed:
        comment += ". Нарушение SLA подтверждено"
    elif was_overdue_before:
        comment += ". Нарушение SLA не критично"
    
    history = IncidentHistory(
        incident_id=incident.id,
        user_id=data.user_id,
        previous_status_id=incident.status_id,
        new_status_id=incident.status_id,
        comment=comment
    )
    db.add(history)
    
    await db.commit()
    
    return {
        "message": "Дедлайн изменён",
        "old_deadline": old_deadline.isoformat() if old_deadline else None,
        "new_deadline": data.new_deadline.isoformat()
    }


@router.post("/reset-executor/{user_id}")
async def reset_executor_incidents(user_id: str, reason: str = "user_deactivated", db=Depends(get_db)):
    """
    Сбросить все инциденты пользователя в статус "Новый".
    
    Вызывается при блокировке/удалении пользователя.
    """
    # Get "New" status
    new_status = await get_status_by_name(db, "Новый")
    if not new_status:
        raise HTTPException(status_code=500, detail="Status 'Новый' not found")
    
    # Find all incidents where user is executor and status is not Closed
    closed_status = await get_status_by_name(db, "Закрыт")
    closed_status_id = closed_status.id if closed_status else None
    
    query = select(Incident).where(Incident.executor_id == user_id)
    if closed_status_id:
        query = query.where(Incident.status_id != closed_status_id)
    
    result = await db.execute(query)
    incidents = result.scalars().all()
    
    reset_count = 0
    for incident in incidents:
        # Skip if already in "New" status
        if incident.status_id == new_status.id:
            continue
        
        # Add history entry
        old_status = incident.status
        history = IncidentHistory(
            incident_id=incident.id,
            user_id=None,  # System action
            previous_status_id=incident.status_id,
            new_status_id=new_status.id,
            comment=f"Исполнитель заблокирован/удалён. Инцидент возвращён в статус 'Новый'"
        )
        db.add(history)
        
        # Reset incident
        incident.executor_id = None
        incident.status_id = new_status.id
        incident.assigned_at = None
        reset_count += 1
    
    await db.commit()
    
    return {"reset_count": reset_count, "message": f"Reset {reset_count} incidents to 'New' status"}


@router.delete("/{incident_id}")
async def delete_incident(
    incident_id: str, 
    user_id: str = None,  # ID пользователя, который удаляет
    user_role: str = None,  # Роль пользователя
    user_department_id: str = None,  # ID отдела пользователя
    db: AsyncSession = Depends(get_db)
):
    """Delete incident with permission check
    
    Permissions:
    - Admin: can delete any incident
    - Manager: can delete incidents from their department only
    - User: can delete only incidents they created AND only if status is "Новый"
    - Executor: cannot delete incidents
    """
    result = await db.execute(
        select(Incident)
        .options(
            selectinload(Incident.status),
            selectinload(Incident.department)
        )
        .where(Incident.id == incident_id)
    )
    incident = result.scalar_one_or_none()
    
    if not incident:
        raise HTTPException(status_code=404, detail="Инцидент не найден")
    
    # Check permissions based on role
    if user_role == "Admin":
        # Admin can delete any incident
        pass
    elif user_role == "Manager":
        # Manager can delete only incidents from their department
        if str(incident.department_id) != user_department_id:
            raise HTTPException(
                status_code=403, 
                detail="Вы можете удалять только инциденты своего отдела"
            )
    elif user_role == "User":
        # User can delete only incidents they created AND only if status is "Новый"
        if str(incident.initiator_id) != user_id:
            raise HTTPException(
                status_code=403,
                detail="Вы можете удалять только инциденты, которые создали вы"
            )
        if incident.status.name != "Новый":
            raise HTTPException(
                status_code=403,
                detail="Вы можете удалять только инциденты в статусе 'Новый'"
            )
    else:
        # Executor and other roles cannot delete
        raise HTTPException(
            status_code=403,
            detail="У вас нет прав на удаление инцидентов"
        )
    
    # Delete related records (history, comments, attachments, notifications)
    # Note: In production, consider using CASCADE delete in DB or soft delete
    
    # Delete incident history
    await db.execute(
        IncidentHistory.__table__.delete().where(IncidentHistory.incident_id == incident_id)
    )
    
    # Delete comments
    from shared.models import Comment
    await db.execute(
        Comment.__table__.delete().where(Comment.incident_id == incident_id)
    )
    
    # Delete attachments
    from shared.models import Attachment
    await db.execute(
        Attachment.__table__.delete().where(Attachment.incident_id == incident_id)
    )
    
    # Delete notifications
    await db.execute(
        Notification.__table__.delete().where(Notification.incident_id == incident_id)
    )
    
    # Delete the incident
    await db.execute(
        Incident.__table__.delete().where(Incident.id == incident_id)
    )
    
    await db.commit()
    
    return {"message": "Инцидент удалён"}
