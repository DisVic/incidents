"""
Пакет shared — общие модули для всех микросервисов.

Содержит:
- Конфигурация (config.py)
- Модели базы данных (models.py)
- Утилиты: хеширование, JWT, SLA-расчёты (utils.py)
- Celery-задачи для фоновой обработки (tasks.py)
- Скрипты инициализации БД (init_db.py, reset_admin.py)
"""
from shared.config import settings
from shared.database import get_db, async_session
from shared.models import Base
from shared.utils import (
    hash_password, verify_password,
    create_access_token, create_refresh_token, decode_token,
    calculate_sla_deadline, get_sla_percentage
)

__all__ = [
    "settings",
    "get_db",
    "async_session",
    "Base",
    "hash_password",
    "verify_password",
    "create_access_token",
    "create_refresh_token",
    "decode_token",
    "calculate_sla_deadline",
    "get_sla_percentage",
]
