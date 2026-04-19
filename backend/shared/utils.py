"""
Вспомогательные функции для всех микросервисов
"""
import uuid
from datetime import datetime, timedelta
from typing import Optional, List
from jose import jwt, JWTError
from passlib.context import CryptContext

# Настройка хеширования паролей через bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    # Хеширует пароль для хранения в БД
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    # Проверяет пароль против хеша из БД
    return pwd_context.verify(plain_password, hashed_password)


# === JWT-токены для авторизации ===

def create_access_token(user_id: uuid.UUID, role: str, secret_key: str, algorithm: str = "HS256",
                        expire_minutes: int = 30) -> str:
    # Создаёт access-токен для API-запросов (живёт 30 мин по умолчанию)
    expire = datetime.utcnow() + timedelta(minutes=expire_minutes)
    payload = {"sub": str(user_id), "exp": expire, "role": role}
    return jwt.encode(payload, secret_key, algorithm=algorithm)


def create_refresh_token(user_id: uuid.UUID, secret_key: str, algorithm: str = "HS256",
                         expire_days: int = 7) -> str:
    # Создаёт refresh-токен для обновления access-токена (живёт 7 дней)
    expire = datetime.utcnow() + timedelta(days=expire_days)
    payload = {"sub": str(user_id), "exp": expire, "type": "refresh"}
    return jwt.encode(payload, secret_key, algorithm=algorithm)


def decode_token(token: str, secret_key: str, algorithm: str = "HS256") -> Optional[dict]:
    # Декодирует JWT-токен, возвращает payload или None если невалиден
    try:
        return jwt.decode(token, secret_key, algorithms=[algorithm])
    except JWTError:
        return None


# === Расчёт SLA с учётом рабочих часов (9:00-18:00, Пн-Пт) ===

def calculate_sla_deadline(
    created_at: datetime,
    resolution_hours: int,
    work_hour_start: int = 9,
    work_hour_end: int = 18,
    work_days: List[int] = None
) -> datetime:
    """
    Рассчитывает дедлайн SLA с учётом только рабочих часов.
    Выходные и праздники НЕ учитываются.
    
    Пример: инцидент создан в Пт 17:00, SLA 4ч → дедлайн Пн 12:00
    """
    if work_days is None:
        work_days = [0, 1, 2, 3, 4]  # Пн-Пт
    
    WORK_HOURS_PER_DAY = work_hour_end - work_hour_start  # 9 часов
    remaining_hours = resolution_hours
    current = created_at
    
    while remaining_hours > 0:
        # Пропускаем выходные
        if current.weekday() not in work_days:
            days_to_add = 7 - current.weekday() if current.weekday() == 5 else 1
            current = current + timedelta(days=days_to_add)
            current = current.replace(hour=work_hour_start, minute=0, second=0, microsecond=0)
            continue
        
        # Границы рабочего дня
        work_day_start = current.replace(hour=work_hour_start, minute=0, second=0, microsecond=0)
        work_day_end = current.replace(hour=work_hour_end, minute=0, second=0, microsecond=0)
        
        # Если сейчас до начала рабочего дня — сдвигаем на начало
        if current < work_day_start:
            current = work_day_start
        
        # Если после конца рабочего дня — сдвигаем на следующий рабочий день
        if current >= work_day_end:
            current = current + timedelta(days=1)
            if current.weekday() not in work_days:
                continue
            current = current.replace(hour=work_hour_start, minute=0, second=0, microsecond=0)
            continue
        
        # Сколько рабочих часов осталось сегодня
        hours_left_today = (work_day_end - current).total_seconds() / 3600
        
        if remaining_hours <= hours_left_today:
            # Дедлайн сегодня
            deadline = current + timedelta(hours=remaining_hours)
            if deadline.hour >= work_hour_end:
                deadline = deadline.replace(hour=work_hour_end, minute=0, second=0, microsecond=0)
            return deadline
        else:
            # Переходим на следующий рабочий день
            remaining_hours -= hours_left_today
            current = current + timedelta(days=1)
            current = current.replace(hour=work_hour_start, minute=0, second=0, microsecond=0)
            # Пропускаем выходные
            while current.weekday() not in work_days:
                current = current + timedelta(days=1)
    
    return current


def get_sla_percentage(created_at: datetime, deadline: datetime) -> float:
    # Возвращает % использованного времени SLA (0-100+)
    total_time = (deadline - created_at).total_seconds()
    elapsed = (datetime.utcnow() - created_at).total_seconds()
    return min(100.0, (elapsed / total_time) * 100) if total_time > 0 else 100.0


def get_sla_remaining_time(deadline: datetime, now: datetime = None) -> dict:
    """
    Возвращает оставшееся время до дедлайна SLA.
    Формат: {"total_seconds": ..., "is_overdue": bool, "formatted": "2 д. 4 ч."}
    """
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
    """
    Возвращает цвет для индикатора SLA:
    - green: < 60% использовано
    - yellow: 60-80%
    - orange: 80-100%
    - red: просрочен или > 100%
    """
    if is_overdue or percentage >= 100:
        return "red"
    elif percentage >= 80:
        return "orange"
    elif percentage >= 60:
        return "yellow"
    else:
        return "green"