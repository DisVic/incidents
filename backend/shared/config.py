"""
Конфигурация приложения — чтение из .env или дефолтные значения.

Используется pydantic-settings для автоматической валидации и загрузки.
Все микросервисы импортируют settings из этого модуля.
"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # === Основное ===
    APP_NAME: str = "Incident Management System"
    DEBUG: bool = True  # Включить подробное логирование
    
    # === База данных ===
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@postgres:5432/incidents"
    
    # === Redis для Celery ===
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # === JWT-авторизация ===
    SECRET_KEY: str = "your-secret-key-change-in-production"  # В проде обязательно менять!
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30  # Access-токен живёт 30 минут
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7     # Refresh-токен живёт 7 дней
    
    # === SLA: рабочие часы ===
    WORK_HOUR_START: int = 9   # Начало рабочего дня
    WORK_HOUR_END: int = 18    # Конец рабочего дня
    WORK_DAYS: list[int] = [0, 1, 2, 3, 4]  # Пн-Пт (0=Понедельник)
    
    # === Email (SMTP) ===
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: Optional[int] = None
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM: Optional[str] = None
    
    # === Frontend URL для ссылок в письмах ===
    FRONTEND_URL: str = "http://localhost:3000"
    
    # === Загрузка файлов ===
    UPLOAD_DIR: str = "uploads"
    MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10 MB
    ALLOWED_EXTENSIONS: list[str] = ["jpg", "jpeg", "png", "gif", "pdf", "doc", "docx", "xls", "xlsx", "txt", "log"]
    
    # === URL микросервисов (для межсервисного взаимодействия) ===
    USER_SERVICE_URL: str = "http://user-service:8001"
    INCIDENT_SERVICE_URL: str = "http://incident-service:8002"
    SLA_SERVICE_URL: str = "http://sla-service:8003"
    NOTIFICATION_SERVICE_URL: str = "http://notification-service:8004"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# Глобальный экземпляр настроек — импортируется во все сервисы
settings = Settings()