"""
Incident Service - Управление инцидентами
"""
import uuid
from datetime import datetime, timedelta
from io import BytesIO, StringIO

from fastapi import FastAPI, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func, and_, or_, case
from sqlalchemy.orm import selectinload

from routers import incidents, comments, reference
from shared import settings, get_db
from shared.models import Incident, Status, Priority, Department, User, SLAPolicy

app = FastAPI(
    title="Incident Service",
    version="1.0.0",
    description="Управление инцидентами, комментариями и справочниками",
    root_path="/incident",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(incidents.router, prefix="/incidents", tags=["Incidents"])
app.include_router(comments.router, prefix="/comments", tags=["Comments"])
app.include_router(reference.router, prefix="/reference", tags=["Reference"])


@app.get("/health")
async def health():
    return {"service": "incident-service", "status": "healthy"}


@app.get("/reports/dashboard")
async def dashboard(
    department_id: str = None,
    date_from: str = None,
    date_to: str = None,
    db=Depends(get_db)
):
    """Dashboard statistics with optional date range filter"""
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    week_start = now - timedelta(days=7)
    
    # Parse date range
    from_date = None
    to_date = None
    if date_from:
        try:
            from_date = datetime.strptime(date_from, "%Y-%m-%d")
        except ValueError:
            pass
    if date_to:
        try:
            to_date = datetime.strptime(date_to, "%Y-%m-%d")
            to_date = to_date.replace(hour=23, minute=59, second=59)
        except ValueError:
            pass
    
    # Base filter for department
    dept_filter = []
    if department_id:
        dept_filter = [Incident.department_id == uuid.UUID(department_id)]
    
    # Date range filter
    date_filter = []
    if from_date:
        date_filter.append(Incident.created_at >= from_date)
    if to_date:
        date_filter.append(Incident.created_at <= to_date)
    
    # Total incidents
    query = select(func.count()).select_from(Incident)
    if dept_filter:
        query = query.where(*dept_filter)
    if date_filter:
        query = query.where(*date_filter)
    total_result = await db.execute(query)
    total_incidents = total_result.scalar()
    
    # Get status IDs
    new_result = await db.execute(select(Status.id).where(Status.name == "Новый"))
    new_status_id = new_result.scalar_one_or_none()
    
    in_progress_result = await db.execute(select(Status.id).where(Status.name == "В работе"))
    in_progress_status_id = in_progress_result.scalar_one_or_none()
    
    resolved_result = await db.execute(select(Status.id).where(Status.name == "Решён"))
    resolved_status_id = resolved_result.scalar_one_or_none()
    
    # Count by status
    new_count = 0
    in_progress_count = 0
    resolved_count = 0
    
    if new_status_id:
        query = select(func.count()).select_from(Incident).where(Incident.status_id == new_status_id)
        if dept_filter:
            query = query.where(*dept_filter)
        if date_filter:
            query = query.where(*date_filter)
        result = await db.execute(query)
        new_count = result.scalar()
    
    if in_progress_status_id:
        query = select(func.count()).select_from(Incident).where(Incident.status_id == in_progress_status_id)
        if dept_filter:
            query = query.where(*dept_filter)
        if date_filter:
            query = query.where(*date_filter)
        result = await db.execute(query)
        in_progress_count = result.scalar()
    
    if resolved_status_id:
        query = select(func.count()).select_from(Incident).where(Incident.status_id == resolved_status_id)
        if dept_filter:
            query = query.where(*dept_filter)
        if date_filter:
            query = query.where(*date_filter)
        result = await db.execute(query)
        resolved_count = result.scalar()
    
    # Overdue
    query = select(func.count()).select_from(Incident).where(Incident.overdue == True)
    if dept_filter:
        query = query.where(*dept_filter)
    if date_filter:
        query = query.where(*date_filter)
    overdue_result = await db.execute(query)
    overdue_count = overdue_result.scalar()
    
    # Today (only if no custom date range)
    today_count = 0
    if not date_filter:
        query = select(func.count()).select_from(Incident).where(Incident.created_at >= today_start)
        if dept_filter:
            query = query.where(*dept_filter)
        today_result = await db.execute(query)
        today_count = today_result.scalar()
    
    # This month (only if no custom date range)
    month_count = 0
    if not date_filter:
        query = select(func.count()).select_from(Incident).where(Incident.created_at >= month_start)
        if dept_filter:
            query = query.where(*dept_filter)
        month_result = await db.execute(query)
        month_count = month_result.scalar()
    
    # Resolved this week (only if no custom date range)
    resolved_week_count = 0
    if not date_filter:
        query = select(func.count()).select_from(Incident).where(
            Incident.resolved_at >= week_start,
            Incident.resolved_at.isnot(None)
        )
        if dept_filter:
            query = query.where(*dept_filter)
        resolved_week_result = await db.execute(query)
        resolved_week_count = resolved_week_result.scalar()
    
    # Average resolution time
    query = select(func.avg(
        func.extract('epoch', Incident.resolved_at - Incident.created_at) / 3600
    )).where(Incident.resolved_at.isnot(None))
    if dept_filter:
        query = query.where(*dept_filter)
    if date_filter:
        query = query.where(*date_filter)
    avg_result = await db.execute(query)
    avg_hours = avg_result.scalar()
    
    return {
        "total_incidents": total_incidents,
        "new_incidents": new_count,
        "in_progress_incidents": in_progress_count,
        "resolved_incidents": resolved_count,
        "overdue_incidents": overdue_count,
        "incidents_today": today_count,
        "incidents_this_month": month_count,
        "resolved_this_week": resolved_week_count,
        "avg_resolution_time_hours": round(avg_hours, 1) if avg_hours else None
    }


@app.get("/reports/sla-stats")
async def sla_stats(
    department_id: str = None,
    date_from: str = None,
    date_to: str = None,
    db=Depends(get_db)
):
    """SLA statistics: on_time, overdue, near_deadline"""
    now = datetime.utcnow()
    
    # Parse date range
    from_date = None
    to_date = None
    if date_from:
        try:
            from_date = datetime.strptime(date_from, "%Y-%m-%d")
        except ValueError:
            pass
    if date_to:
        try:
            to_date = datetime.strptime(date_to, "%Y-%m-%d")
            to_date = to_date.replace(hour=23, minute=59, second=59)
        except ValueError:
            pass
    
    # Base filter for department
    dept_filter = []
    if department_id:
        dept_filter = [Incident.department_id == uuid.UUID(department_id)]
    
    # Date range filter
    date_filter = []
    if from_date:
        date_filter.append(Incident.created_at >= from_date)
    if to_date:
        date_filter.append(Incident.created_at <= to_date)
    
    # Get closed incidents (resolved or closed)
    closed_result = await db.execute(
        select(Status.id).where(Status.name.in_(["Решён", "Закрыт"]))
    )
    closed_ids = [row[0] for row in closed_result.fetchall()]
    
    # Active statuses
    active_result = await db.execute(
        select(Status.id).where(Status.name.in_(["Новый", "Назначен", "В работе"]))
    )
    active_ids = [row[0] for row in active_result.fetchall()]
    
    # Overdue count: active with (overdue=True OR was_overdue=True) OR closed with was_overdue=True
    # Active overdue
    active_overdue_count = 0
    if active_ids:
        query = select(func.count()).select_from(Incident).where(
            Incident.status_id.in_(active_ids),
            or_(Incident.overdue == True, Incident.was_overdue == True)
        )
        if dept_filter:
            query = query.where(*dept_filter)
        if date_filter:
            query = query.where(*date_filter)
        result = await db.execute(query)
        active_overdue_count = result.scalar() or 0
    
    # Closed overdue (was_overdue=True)
    closed_overdue_count = 0
    if closed_ids:
        query = select(func.count()).select_from(Incident).where(
            Incident.status_id.in_(closed_ids),
            Incident.was_overdue == True
        )
        if dept_filter:
            query = query.where(*dept_filter)
        if date_filter:
            query = query.where(*date_filter)
        result = await db.execute(query)
        closed_overdue_count = result.scalar() or 0
    
    overdue_count = active_overdue_count + closed_overdue_count
    
    # Near deadline (active incidents with < 20% time remaining, not overdue)
    near_deadline_count = 0
    if active_ids:
        query = select(Incident).where(
            Incident.status_id.in_(active_ids),
            Incident.overdue == False,
            Incident.was_overdue == False
        )
        if dept_filter:
            query = query.where(*dept_filter)
        if date_filter:
            query = query.where(*date_filter)
        active_incidents = await db.execute(query)
        for incident in active_incidents.scalars().all():
            if incident.sla_deadline:
                total_time = (incident.sla_deadline - incident.created_at).total_seconds()
                elapsed = (now - incident.created_at).total_seconds()
                if total_time > 0:
                    percentage = (elapsed / total_time) * 100
                    if percentage >= 80:
                        near_deadline_count += 1
    
    # On time: closed with was_overdue=False + active without overdue/was_overdue
    on_time_count = 0
    if closed_ids:
        query = select(func.count()).select_from(Incident).where(
            Incident.status_id.in_(closed_ids),
            Incident.was_overdue == False
        )
        if dept_filter:
            query = query.where(*dept_filter)
        if date_filter:
            query = query.where(*date_filter)
        on_time_result = await db.execute(query)
        on_time_count = on_time_result.scalar() or 0
    
    # Active on time (not overdue and not was_overdue)
    if active_ids:
        query = select(func.count()).select_from(Incident).where(
            Incident.status_id.in_(active_ids),
            Incident.overdue == False,
            Incident.was_overdue == False
        )
        if dept_filter:
            query = query.where(*dept_filter)
        if date_filter:
            query = query.where(*date_filter)
        active_on_time_result = await db.execute(query)
        on_time_count += active_on_time_result.scalar() or 0
    
    return {
        "on_time": on_time_count,
        "overdue": overdue_count,
        "near_deadline": near_deadline_count
    }


@app.get("/reports/overdue-incidents")
async def overdue_incidents_list(
    department_id: str = None,
    limit: int = 50,
    db=Depends(get_db)
):
    """List of overdue incidents with details for history/tracking"""
    # Get status IDs
    closed_result = await db.execute(
        select(Status.id).where(Status.name.in_(["Решён", "Закрыт"]))
    )
    closed_ids = [row[0] for row in closed_result.fetchall()]
    
    active_result = await db.execute(
        select(Status.id).where(Status.name.in_(["Новый", "Назначен", "В работе"]))
    )
    active_ids = [row[0] for row in active_result.fetchall()]
    
    # Query overdue incidents with executor and department info
    query = select(Incident).options(
        selectinload(Incident.executor),
        selectinload(Incident.department),
        selectinload(Incident.status),
        selectinload(Incident.priority)
    ).where(
        or_(
            # Active with overdue or was_overdue
            and_(Incident.status_id.in_(active_ids), or_(Incident.overdue == True, Incident.was_overdue == True)),
            # Closed with was_overdue
            and_(Incident.status_id.in_(closed_ids), Incident.was_overdue == True)
        )
    ).order_by(Incident.created_at.desc()).limit(limit)
    
    if department_id:
        query = query.where(Incident.department_id == uuid.UUID(department_id))
    
    result = await db.execute(query)
    incidents = result.scalars().all()
    
    now = datetime.utcnow()
    data = []
    for inc in incidents:
        # Calculate overdue hours
        if inc.resolved_at and inc.sla_deadline:
            overdue_hours = (inc.resolved_at - inc.sla_deadline).total_seconds() / 3600
        elif inc.closed_at and inc.sla_deadline:
            overdue_hours = (inc.closed_at - inc.sla_deadline).total_seconds() / 3600
        elif inc.sla_deadline:
            overdue_hours = (now - inc.sla_deadline).total_seconds() / 3600
        else:
            overdue_hours = 0
        
        data.append({
            "id": str(inc.id),
            "title": inc.title,
            "status": inc.status.name if inc.status else None,
            "executor_id": str(inc.executor_id) if inc.executor_id else None,
            "executor_name": inc.executor.full_name if inc.executor else None,
            "department": inc.department.name if inc.department else None,
            "priority": inc.priority.name if inc.priority else None,
            "sla_deadline": inc.sla_deadline.isoformat() if inc.sla_deadline else None,
            "resolved_at": inc.resolved_at.isoformat() if inc.resolved_at else None,
            "closed_at": inc.closed_at.isoformat() if inc.closed_at else None,
            "created_at": inc.created_at.isoformat() if inc.created_at else None,
            "overdue_hours": round(overdue_hours, 1),
            "is_active": inc.status_id in active_ids if active_ids else False
        })
    
    return {"total": len(data), "incidents": data}


@app.get("/reports/status-stats")
async def status_stats(
    department_id: str = None,
    date_from: str = None,
    date_to: str = None,
    db=Depends(get_db)
):
    """Incident counts by status"""
    # Parse date range
    date_filter = []
    if date_from:
        try:
            from_date = datetime.strptime(date_from, "%Y-%m-%d")
            date_filter.append(Incident.created_at >= from_date)
        except ValueError:
            pass
    if date_to:
        try:
            to_date = datetime.strptime(date_to, "%Y-%m-%d")
            to_date = to_date.replace(hour=23, minute=59, second=59)
            date_filter.append(Incident.created_at <= to_date)
        except ValueError:
            pass
    
    query = select(Status, func.count(Incident.id))\
        .outerjoin(Incident, Status.id == Incident.status_id)
    
    if department_id:
        query = query.where(Incident.department_id == uuid.UUID(department_id))
    
    if date_filter:
        query = query.where(*date_filter)
    
    query = query.group_by(Status.id).order_by(func.count(Incident.id).desc())
    result = await db.execute(query)
    
    return [
        {"name": row[0].name, "count": row[1]}
        for row in result.fetchall()
    ]


@app.get("/reports/activity")
async def activity_stats(
    days: int = 14,
    department_id: str = None,
    date_from: str = None,
    date_to: str = None,
    db=Depends(get_db)
):
    """Incident activity for last N days or custom date range"""
    now = datetime.utcnow()
    
    # Parse date range
    if date_from and date_to:
        try:
            start_date = datetime.strptime(date_from, "%Y-%m-%d")
            end_date = datetime.strptime(date_to, "%Y-%m-%d")
            end_date = end_date.replace(hour=23, minute=59, second=59)
        except ValueError:
            start_date = now - timedelta(days=days)
            end_date = now
    else:
        start_date = now - timedelta(days=days)
        end_date = now
    
    # Base filter for department
    dept_filter = []
    if department_id:
        dept_filter = [Incident.department_id == uuid.UUID(department_id)]
    
    # Get counts per day
    query = select(
        func.date(Incident.created_at).label('date'),
        func.count(Incident.id).label('count')
    ).where(Incident.created_at >= start_date).where(Incident.created_at <= end_date)
    
    if dept_filter:
        query = query.where(*dept_filter)
    
    query = query.group_by(func.date(Incident.created_at)).order_by(func.date(Incident.created_at))
    result = await db.execute(query)
    
    # Create a dict of existing data
    data_dict = {}
    for row in result.fetchall():
        data_dict[str(row[0])] = row[1]
    
    # Fill in all days
    activity = []
    current = start_date
    while current <= end_date:
        date_str = current.strftime('%Y-%m-%d')
        activity.append({
            "date": date_str,
            "count": data_dict.get(date_str, 0)
        })
        current += timedelta(days=1)
    
    return activity


@app.get("/reports/executors")
async def executors_stats(
    days: int = 30,
    limit: int = 5,
    department_id: str = None,
    date_from: str = None,
    date_to: str = None,
    db=Depends(get_db)
):
    """Top executors by resolved incidents"""
    now = datetime.utcnow()
    
    # Parse date range
    if date_from and date_to:
        try:
            start_date = datetime.strptime(date_from, "%Y-%m-%d")
            end_date = datetime.strptime(date_to, "%Y-%m-%d")
            end_date = end_date.replace(hour=23, minute=59, second=59)
        except ValueError:
            start_date = now - timedelta(days=days)
            end_date = now
    else:
        start_date = now - timedelta(days=days)
        end_date = now
    
    # Base filter for department
    dept_filter = []
    if department_id:
        dept_filter = [Incident.department_id == uuid.UUID(department_id)]
    
    # Get resolved status
    resolved_result = await db.execute(select(Status.id).where(Status.name == "Решён"))
    resolved_id = resolved_result.scalar_one_or_none()
    
    closed_result = await db.execute(select(Status.id).where(Status.name == "Закрыт"))
    closed_id = closed_result.scalar_one_or_none()
    
    resolved_ids = [resolved_id, closed_id]
    resolved_ids = [rid for rid in resolved_ids if rid]
    
    if not resolved_ids:
        return []
    
    # Count resolved incidents per executor
    query = select(User, func.count(Incident.id).label('resolved_count'))\
        .join(Incident, User.id == Incident.executor_id)\
        .where(
            Incident.resolved_at >= start_date,
            Incident.resolved_at <= end_date,
            Incident.resolved_at.isnot(None)
        )
    
    if dept_filter:
        query = query.where(*dept_filter)
    
    query = query.group_by(User.id).order_by(func.count(Incident.id).desc()).limit(limit)
    result = await db.execute(query)
    
    executors = []
    for row in result.fetchall():
        user = row[0]
        count = row[1]
        executors.append({
            "id": str(user.id),
            "full_name": user.full_name,
            "resolved_count": count
        })
    
    return executors


@app.get("/reports/departments")
async def departments_report(
    date_from: str = None,
    date_to: str = None,
    db=Depends(get_db)
):
    """Report by departments"""
    # Get statuses
    new_result = await db.execute(select(Status.id).where(Status.name == "Новый"))
    new_id = new_result.scalar_one_or_none()
    
    in_progress_result = await db.execute(select(Status.id).where(Status.name == "В работе"))
    in_progress_id = in_progress_result.scalar_one_or_none()
    
    resolved_result = await db.execute(select(Status.id).where(Status.name == "Решён"))
    resolved_id = resolved_result.scalar_one_or_none()
    
    # Build query
    # For overdue: was_overdue (confirmed by manager or frozen at close) OR overdue (currently overdue for active)
    query = select(
        Department.id,
        Department.name,
        func.count(Incident.id).label('total_incidents'),
        func.sum(case((Incident.status_id == new_id, 1), else_=0)).label('new_count'),
        func.sum(case((Incident.status_id == in_progress_id, 1), else_=0)).label('in_progress_count'),
        func.sum(case((Incident.status_id == resolved_id, 1), else_=0)).label('resolved_count'),
        func.sum(case(
            (Incident.was_overdue == True, 1),  # Confirmed or frozen
            else_=case((Incident.overdue == True, 1), else_=0)  # Currently overdue
        )).label('overdue_count'),
        func.avg(
            case(
                (Incident.resolved_at.isnot(None),
                 func.extract('epoch', Incident.resolved_at - Incident.created_at) / 3600),
                else_=None
            )
        ).label('avg_resolution_time_hours')
    ).join(Incident, Department.id == Incident.department_id).group_by(Department.id, Department.name)
    
    # Apply date filters
    if date_from:
        try:
            from_date = datetime.strptime(date_from, "%Y-%m-%d")
            query = query.where(Incident.created_at >= from_date)
        except ValueError:
            pass
    
    if date_to:
        try:
            to_date = datetime.strptime(date_to, "%Y-%m-%d")
            to_date = to_date.replace(hour=23, minute=59, second=59)
            query = query.where(Incident.created_at <= to_date)
        except ValueError:
            pass
    
    result = await db.execute(query)
    
    return [
        {
            "department_id": str(row[0]),
            "department_name": row[1],
            "total_incidents": row[2] or 0,
            "new_count": row[3] or 0,
            "in_progress_count": row[4] or 0,
            "resolved_count": row[5] or 0,
            "overdue_count": row[6] or 0,
            "avg_resolution_time_hours": round(row[7], 1) if row[7] else None
        }
        for row in result.fetchall()
    ]


@app.get("/reports/sla-analytics")
async def sla_analytics(
    date_from: str = None,
    date_to: str = None,
    department_id: str = None,
    db=Depends(get_db)
):
    """SLA analytics with problem zones"""
    now = datetime.utcnow()
    
    # Build base query
    query = select(Incident).options(
        selectinload(Incident.priority),
        selectinload(Incident.department)
    )
    
    # Apply filters
    if date_from:
        try:
            from_date = datetime.strptime(date_from, "%Y-%m-%d")
            query = query.where(Incident.created_at >= from_date)
        except ValueError:
            pass
    
    if date_to:
        try:
            to_date = datetime.strptime(date_to, "%Y-%m-%d")
            to_date = to_date.replace(hour=23, minute=59, second=59)
            query = query.where(Incident.created_at <= to_date)
        except ValueError:
            pass
    
    if department_id:
        query = query.where(Incident.department_id == department_id)
    
    result = await db.execute(query)
    incidents = result.scalars().all()
    
    # For statistics: was_overdue OR overdue counts as overdue
    total_incidents = len(incidents)
    overdue_count = sum(1 for i in incidents if i.was_overdue or i.overdue)
    on_time_count = total_incidents - overdue_count
    
    # Calculate average resolution time
    resolution_times = [
        (i.resolved_at - i.created_at).total_seconds() / 3600
        for i in incidents if i.resolved_at
    ]
    avg_resolution_time = sum(resolution_times) / len(resolution_times) if resolution_times else 0
    
    # Find problem zones (departments with high overdue rate)
    dept_stats = {}
    for inc in incidents:
        dept_name = inc.department.name if inc.department else "Без отдела"
        if dept_name not in dept_stats:
            dept_stats[dept_name] = {"total": 0, "overdue": 0}
        dept_stats[dept_name]["total"] += 1
        # was_overdue OR overdue
        if inc.was_overdue or inc.overdue:
            dept_stats[dept_name]["overdue"] += 1
    
    problem_zones = []
    for name, stats in dept_stats.items():
        if stats["total"] > 0:
            overdue_percent = round(stats["overdue"] / stats["total"] * 100, 1)
            if overdue_percent >= 20:  # More than 20% overdue is a problem
                problem_zones.append({
                    "name": name,
                    "overdue_count": stats["overdue"],
                    "overdue_percent": overdue_percent
                })
    
    # Sort by overdue percent
    problem_zones.sort(key=lambda x: -x["overdue_percent"])
    
    return {
        "total_incidents": total_incidents,
        "on_time_count": on_time_count,
        "on_time_percent": round(on_time_count / total_incidents * 100, 1) if total_incidents > 0 else 0,
        "overdue_count": overdue_count,
        "overdue_percent": round(overdue_count / total_incidents * 100, 1) if total_incidents > 0 else 0,
        "avg_resolution_time_hours": round(avg_resolution_time, 1),
        "problem_zones": problem_zones[:5]
    }


@app.get("/reports/executors-detailed")
async def executors_detailed(
    date_from: str = None,
    date_to: str = None,
    department_id: str = None,
    manager_view: bool = False,
    db=Depends(get_db)
):
    """Detailed executors report
    
    manager_view: if True, shows executors from specified department + all Admins
    """
    from shared.models import Role
    
    # Get statuses
    resolved_result = await db.execute(select(Status.id).where(Status.name.in_(["Решён", "Закрыт"])))
    resolved_ids = [row[0] for row in resolved_result.fetchall()]
    
    # Get Admin role ID for manager_view
    admin_role_id = None
    if manager_view and department_id:
        admin_result = await db.execute(select(Role.id).where(Role.name == "Admin"))
        admin_role_id = admin_result.scalar_one_or_none()
    
    # Build query
    # For overdue: was_overdue (confirmed/frozen) OR overdue (currently overdue)
    query = select(
        User.id,
        User.full_name,
        User.role_id,
        Department.name.label('department_name'),
        func.count(Incident.id).label('total_assigned'),
        func.sum(case((Incident.status_id.in_(resolved_ids), 1), else_=0)).label('total_resolved'),
        func.sum(case(
            (Incident.was_overdue == True, 1),
            else_=case((Incident.overdue == True, 1), else_=0)
        )).label('overdue_count'),
        func.avg(
            case(
                (Incident.resolved_at.isnot(None),
                 func.extract('epoch', Incident.resolved_at - Incident.created_at) / 3600),
                else_=None
            )
        ).label('avg_resolution_time_hours')
    ).join(Incident, User.id == Incident.executor_id).outerjoin(
        Department, User.department_id == Department.id
    ).group_by(User.id, User.full_name, User.role_id, Department.name)
    
    # Apply filters
    if date_from:
        try:
            from_date = datetime.strptime(date_from, "%Y-%m-%d")
            query = query.where(Incident.created_at >= from_date)
        except ValueError:
            pass
    
    if date_to:
        try:
            to_date = datetime.strptime(date_to, "%Y-%m-%d")
            to_date = to_date.replace(hour=23, minute=59, second=59)
            query = query.where(Incident.created_at <= to_date)
        except ValueError:
            pass
    
    # Filter by department
    if manager_view and department_id and admin_role_id:
        # Manager view: show department executors + all Admins
        query = query.where(
            (User.department_id == department_id) | (User.role_id == admin_role_id)
        )
    elif department_id:
        # Regular filter by department
        query = query.where(User.department_id == department_id)
    
    result = await db.execute(query)
    
    data = []
    for row in result.fetchall():
        # row indices: 0=id, 1=full_name, 2=role_id, 3=department_name, 4=total_assigned, 5=total_resolved, 6=overdue_count, 7=avg_resolution_time_hours
        total = int(row[4] or 0)
        overdue = int(row[6] or 0)
        sla_compliance = round((total - overdue) / total * 100, 1) if total > 0 else 100
        
        data.append({
            "executor_id": str(row[0]),
            "executor_name": row[1],
            "department_name": row[3] or "Без отдела",
            "total_assigned": total,
            "total_resolved": int(row[5] or 0),
            "overdue_count": overdue,
            "avg_resolution_time_hours": round(float(row[7]), 1) if row[7] else None,
            "sla_compliance": sla_compliance
        })
    
    return sorted(data, key=lambda x: -x['total_resolved'])


@app.get("/reports/user/{user_id}")
async def user_stats(
    user_id: str,
    period: str = Query("month", regex="^(month|quarter|year)$"),
    date_from: str = None,
    date_to: str = None,
    db=Depends(get_db)
):
    """Detailed statistics for a specific user/executor"""
    from datetime import timezone
    
    # Calculate date range based on period or custom dates
    now = datetime.utcnow()
    
    # Use custom date range if provided
    if date_from and date_to:
        try:
            start_date = datetime.strptime(date_from, "%Y-%m-%d")
            end_date = datetime.strptime(date_to, "%Y-%m-%d")
            end_date = end_date.replace(hour=23, minute=59, second=59)
        except ValueError:
            # Fallback to period
            if period == "month":
                start_date = now - timedelta(days=30)
            elif period == "quarter":
                start_date = now - timedelta(days=90)
            else:
                start_date = now - timedelta(days=365)
            end_date = now
    else:
        # Use predefined period
        if period == "month":
            start_date = now - timedelta(days=30)
        elif period == "quarter":
            start_date = now - timedelta(days=90)
        else:  # year
            start_date = now - timedelta(days=365)
        end_date = now
    
    # Get user info
    user_result = await db.execute(
        select(User).options(selectinload(User.department)).where(User.id == uuid.UUID(user_id))
    )
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    # Get status IDs
    resolved_result = await db.execute(
        select(Status.id).where(Status.name.in_(["Решён", "Закрыт"]))
    )
    resolved_ids = [row[0] for row in resolved_result.fetchall()]
    
    in_progress_result = await db.execute(
        select(Status.id).where(Status.name == "В работе")
    )
    in_progress_id = in_progress_result.scalar_one_or_none()
    
    # Get all incidents for this executor in period
    query = select(Incident).options(
        selectinload(Incident.status),
        selectinload(Incident.priority),
        selectinload(Incident.department)
    ).where(
        Incident.executor_id == uuid.UUID(user_id),
        Incident.created_at >= start_date,
        Incident.created_at <= end_date
    ).order_by(Incident.created_at.desc())
    
    result = await db.execute(query)
    incidents = result.scalars().all()
    
    # Calculate statistics
    total_assigned = len(incidents)
    total_resolved = sum(1 for i in incidents if i.status_id in resolved_ids)
    in_progress_count = sum(1 for i in incidents if i.status_id == in_progress_id)
    overdue_count = sum(1 for i in incidents if i.was_overdue or i.overdue)
    
    # Average resolution time (for resolved incidents)
    resolution_times = [
        (i.resolved_at - i.created_at).total_seconds() / 3600
        for i in incidents if i.resolved_at
    ]
    avg_resolution_time = sum(resolution_times) / len(resolution_times) if resolution_times else 0
    
    # SLA compliance
    sla_compliance = round((total_assigned - overdue_count) / total_assigned * 100, 1) if total_assigned > 0 else 100
    
    # Format incidents for response
    incidents_data = []
    for inc in incidents:
        incidents_data.append({
            "id": str(inc.id),
            "title": inc.title,
            "status": inc.status.name if inc.status else None,
            "priority": inc.priority.name if inc.priority else None,
            "department": inc.department.name if inc.department else None,
            "created_at": inc.created_at.isoformat() if inc.created_at else None,
            "resolved_at": inc.resolved_at.isoformat() if inc.resolved_at else None,
            "sla_deadline": inc.sla_deadline.isoformat() if inc.sla_deadline else None,
            "overdue": inc.overdue or inc.was_overdue,
            "resolution_time_hours": round((inc.resolved_at - inc.created_at).total_seconds() / 3600, 1) if inc.resolved_at else None
        })
    
    return {
        "user_id": str(user.id),
        "user_name": user.full_name,
        "email": user.email,
        "avatar": user.avatar,
        "department": user.department.name if user.department else None,
        "period": period,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "stats": {
            "total_assigned": total_assigned,
            "total_resolved": total_resolved,
            "in_progress": in_progress_count,
            "overdue_count": overdue_count,
            "avg_resolution_time_hours": round(avg_resolution_time, 1),
            "sla_compliance": sla_compliance
        },
        "incidents": incidents_data
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8002, reload=True)
