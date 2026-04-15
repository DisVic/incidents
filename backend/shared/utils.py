"""
Shared utilities for all microservices
"""
import uuid
from datetime import datetime, timedelta
from typing import Optional, List
from jose import jwt, JWTError
from passlib.context import CryptContext

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


# JWT
def create_access_token(user_id: uuid.UUID, role: str, secret_key: str, algorithm: str = "HS256",
                        expire_minutes: int = 30) -> str:
    expire = datetime.utcnow() + timedelta(minutes=expire_minutes)
    payload = {"sub": str(user_id), "exp": expire, "role": role}
    return jwt.encode(payload, secret_key, algorithm=algorithm)


def create_refresh_token(user_id: uuid.UUID, secret_key: str, algorithm: str = "HS256",
                         expire_days: int = 7) -> str:
    expire = datetime.utcnow() + timedelta(days=expire_days)
    payload = {"sub": str(user_id), "exp": expire, "type": "refresh"}
    return jwt.encode(payload, secret_key, algorithm=algorithm)


def decode_token(token: str, secret_key: str, algorithm: str = "HS256") -> Optional[dict]:
    try:
        return jwt.decode(token, secret_key, algorithms=[algorithm])
    except JWTError:
        return None


# SLA calculation with working hours (9:00-18:00, Mon-Fri)
def calculate_sla_deadline(
    created_at: datetime,
    resolution_hours: int,
    work_hour_start: int = 9,
    work_hour_end: int = 18,
    work_days: List[int] = None
) -> datetime:
    """
    Calculate SLA deadline considering working hours.
    Working time: 9:00-18:00 (9 hours per day), Monday-Friday
    Weekends and holidays are NOT counted.
    
    Args:
        created_at: When the incident was created
        resolution_hours: SLA time in WORKING hours
        work_hour_start: Start of working day (default 9)
        work_hour_end: End of working day (default 18)
        work_days: List of weekday numbers (0=Mon, 6=Sun), default [0,1,2,3,4]
    
    Returns:
        Calculated deadline datetime
    """
    if work_days is None:
        work_days = [0, 1, 2, 3, 4]  # Monday to Friday
    
    WORK_HOURS_PER_DAY = work_hour_end - work_hour_start  # 9 hours
    remaining_hours = resolution_hours
    current = created_at
    
    while remaining_hours > 0:
        # Skip weekends
        if current.weekday() not in work_days:
            # Move to next Monday
            days_to_add = 7 - current.weekday() if current.weekday() == 5 else 1
            current = current + timedelta(days=days_to_add)
            current = current.replace(hour=work_hour_start, minute=0, second=0, microsecond=0)
            continue
        
        # Define working day boundaries
        work_day_start = current.replace(hour=work_hour_start, minute=0, second=0, microsecond=0)
        work_day_end = current.replace(hour=work_hour_end, minute=0, second=0, microsecond=0)
        
        # If current time is before working hours, move to start of working day
        if current < work_day_start:
            current = work_day_start
        
        # If current time is after working hours, move to next working day
        if current >= work_day_end:
            current = current + timedelta(days=1)
            # Check if next day is weekend
            if current.weekday() not in work_days:
                continue
            current = current.replace(hour=work_hour_start, minute=0, second=0, microsecond=0)
            continue
        
        # Calculate how many working hours left today
        hours_left_today = (work_day_end - current).total_seconds() / 3600
        
        if remaining_hours <= hours_left_today:
            # Deadline is today
            deadline = current + timedelta(hours=remaining_hours)
            # Ensure deadline is within working hours (round down to end of work day if needed)
            if deadline.hour >= work_hour_end:
                deadline = deadline.replace(hour=work_hour_end, minute=0, second=0, microsecond=0)
            return deadline
        else:
            # Use remaining hours today and move to next working day
            remaining_hours -= hours_left_today
            # Move to next day at start of working hours
            current = current + timedelta(days=1)
            current = current.replace(hour=work_hour_start, minute=0, second=0, microsecond=0)
            # Skip weekends
            while current.weekday() not in work_days:
                current = current + timedelta(days=1)
    
    # Fallback: return start of next working day
    return current


def get_sla_percentage(created_at: datetime, deadline: datetime) -> float:
    """
    Calculate SLA percentage used (considering working hours).
    Returns value from 0 to 100+.
    """
    total_time = (deadline - created_at).total_seconds()
    elapsed = (datetime.utcnow() - created_at).total_seconds()
    return min(100.0, (elapsed / total_time) * 100) if total_time > 0 else 100.0


def get_sla_remaining_time(deadline: datetime, now: datetime = None) -> dict:
    """
    Calculate remaining time until SLA deadline.
    Returns dict with:
    - total_seconds: total seconds remaining (negative if overdue)
    - is_overdue: bool
    - working_hours: remaining working hours
    - formatted: human-readable string like "2 д. 4 ч. 30 мин." or "Просрочен на 1 ч. 20 мин."
    """
    if now is None:
        now = datetime.utcnow()
    
    delta = deadline - now
    total_seconds = delta.total_seconds()
    is_overdue = total_seconds < 0
    
    abs_seconds = abs(total_seconds)
    
    # Calculate working time (simplified - just show actual time difference)
    days = int(abs_seconds // 86400)
    hours = int((abs_seconds % 86400) // 3600)
    minutes = int((abs_seconds % 3600) // 60)
    
    if is_overdue:
        if days > 0:
            formatted = f"Просрочен на {days} д. {hours} ч."
        elif hours > 0:
            formatted = f"Просрочен на {hours} ч. {minutes} мин."
        else:
            formatted = f"Просрочен на {minutes} мин."
    else:
        if days > 0:
            formatted = f"{days} д. {hours} ч. {minutes} мин."
        elif hours > 0:
            formatted = f"{hours} ч. {minutes} мин."
        else:
            formatted = f"{minutes} мин."
    
    return {
        "total_seconds": total_seconds,
        "is_overdue": is_overdue,
        "working_hours": round(abs_seconds / 3600, 1),
        "formatted": formatted,
        "days": days,
        "hours": hours,
        "minutes": minutes
    }


def get_sla_status_color(percentage: float, is_overdue: bool = False) -> str:
    """
    Get color for SLA status indicator.
    - green: < 60% used
    - yellow: 60-80% used  
    - orange: 80-100% used
    - red: overdue or > 100%
    """
    if is_overdue or percentage >= 100:
        return "red"
    elif percentage >= 80:
        return "orange"
    elif percentage >= 60:
        return "yellow"
    else:
        return "green"
