"""
Вспомогательные функции для всех микросервисов
"""
import uuid
from datetime import datetime, timedelta
from typing import Optional
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


# === Расчёт SLA дедлайнов по приоритетам (календарные дни) ===

# Стандартные дедлайны по приоритетам (в днях)
PRIORITY_DEADLINES = {
    "Низкий": 14,      # 14 дней
    "Средний": 7,      # 7 дней
    "Высокий": 3,      # 3 дня
    "Критический": 1   # 1 день
}


def calculate_sla_deadline(
    created_at: datetime,
    resolution_days: int
) -> datetime:
    """
    Рассчитывает дедлайн SLA путём добавления календарных дней.
    Выходные и праздники учитываются (дедлайн сдвигается по календарю).
    
    Пример: инцидент создан в Пт 17:00, SLA 3 дня → дедлайн Пн 17:00
    """
    return created_at + timedelta(days=resolution_days)


def get_resolution_days_by_priority(priority_name: str) -> int:
    """
    Возвращает количество дней для решения по названию приоритета.
    Если приоритет не найден, возвращает 7 дней (по умолчанию).
    """
    return PRIORITY_DEADLINES.get(priority_name, 7)


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