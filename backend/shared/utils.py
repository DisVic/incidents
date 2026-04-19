"""Утилиты для всех микросервисов"""
import uuid
from datetime import datetime, timedelta
from typing import Optional, List
from jose import jwt, JWTError
from passlib.context import CryptContext

# Контекст для хеширования паролей (bcrypt)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Хеширование пароля"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Проверка пароля"""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(user_id: uuid.UUID, role: str, secret_key: str, algorithm: str = "HS256",
                        expire_minutes: int = 30) -> str:
    """Создание access токена"""
    expire = datetime.utcnow() + timedelta(minutes=expire_minutes)
    payload = {"sub": str(user_id), "exp": expire, "role": role}
    return jwt.encode(payload, secret_key, algorithm=algorithm)


def create_refresh_token(user_id: uuid.UUID, secret_key: str, algorithm: str = "HS256",
                         expire_days: int = 7) -> str:
    """Создание refresh токена"""
    expire = datetime.utcnow() + timedelta(days=expire_days)
    payload = {"sub": str(user_id), "exp": expire, "type": "refresh"}
    return jwt.encode(payload, secret_key, algorithm=algorithm)


def decode_token(token: str, secret_key: str, algorithm: str = "HS256") -> Optional[dict]:
    """Декодирование токена"""
    try:
        return jwt.decode(token, secret_key, algorithms=[algorithm])
    except JWTError:
        return None


def calculate_sla_deadline(
    created_at: datetime,
    resolution_hours: int,
    work_hour_start: int = 9,
    work_hour_end: int = 18,
    work_days: List[int] = None
) -> datetime:
    """Расчёт дедлайна SLA с учётом рабочего времени (9-18, пн-пт)"""
    if work_days is None:
        work_days = [0, 1, 2, 3, 4]
    
    remaining_hours = resolution_hours
    current = created_at
    
    while remaining_hours > 0:
        # Пропускаем выходные
        if current.weekday() not in work_days:
            days_to_add = 7 - current.weekday() if current.weekday() == 5 else 1
            current = current + timedelta(days=days_to_add)
            current = current.replace(hour=work_hour_start, minute=0, second=0, microsecond=0)
            continue
        
        work_day_start = current.replace(hour=work_hour_start, minute=0, second=0, microsecond=0)
        work_day_end = current.replace(hour=work_hour_end, minute=0, second=0, microsecond=0)
        
        # Если ещё не начало рабочего дня — переносим на начало
        if current < work_day_start:
            current = work_day_start
        
        # Если рабочий день закончился — переходим к следующему
        if current >= work_day_end:
            current = current + timedelta(days=1)
            if current.weekday() not in work_days:
                continue
            current = current.replace(hour=work_hour_start, minute=0, second=0, microsecond=0)
            continue
        
        hours_left_today = (work_day_end - current).total_seconds() / 3600
        
        if remaining_hours <= hours_left_today:
            deadline = current + timedelta(hours=remaining_hours)
            if deadline.hour >= work_hour_end:
                deadline = deadline.replace(hour=work_hour_end, minute=0, second=0, microsecond=0)
            return deadline
        else:
            remaining_hours -= hours_left_today
            current = current + timedelta(days=1)
            current = current.replace(hour=work_hour_start, minute=0, second=0, microsecond=0)
            while current.weekday() not in work_days:
                current = current + timedelta(days=1)
    
    return current


def get_sla_percentage(created_at: datetime, deadline: datetime) -> float:
    """Процент использования SLA"""
    total_time = (deadline - created_at).total_seconds()
    elapsed = (datetime.utcnow() - created_at).total_seconds()
    return min(100.0, (elapsed / total_time) * 100) if total_time > 0 else 100.0


def get_sla_remaining_time(deadline: datetime, now: datetime = None) -> dict:
    """Оставшееся время до дедлайна SLA"""
    if now is None:
        now = datetime.utcnow()
    
    delta = deadline - now
    total_seconds = delta.total_seconds()
    is_overdue = total_seconds < 0
    
    abs_seconds = abs(total_seconds)
    
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
    """Цвет индикатора SLA: green (<60%), yellow (60-80%), orange (80-100%), red (>100%)"""
    if is_overdue or percentage >= 100:
        return "red"
    elif percentage >= 80:
        return "orange"
    elif percentage >= 60:
        return "yellow"
    else:
        return "green"
