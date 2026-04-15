"""
Shared configuration for all microservices
"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # App
    APP_NAME: str = "Incident Management System"
    DEBUG: bool = True
    
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/incidents_db"
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # JWT
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # SLA defaults
    WORK_HOUR_START: int = 9
    WORK_HOUR_END: int = 18
    WORK_DAYS: list[int] = [0, 1, 2, 3, 4]
    
    # Email (SMTP)
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: Optional[int] = None
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM: Optional[str] = None
    

    
    # Frontend URL (for email links)
    FRONTEND_URL: str = "http://localhost:3000"
    
    # File uploads
    UPLOAD_DIR: str = "uploads"
    MAX_FILE_SIZE: int = 10 * 1024 * 1024
    ALLOWED_EXTENSIONS: list[str] = ["jpg", "jpeg", "png", "gif", "pdf", "doc", "docx", "xls", "xlsx", "txt", "log"]
    
    # Service URLs (for inter-service communication)
    USER_SERVICE_URL: str = "http://user-service:8001"
    INCIDENT_SERVICE_URL: str = "http://incident-service:8002"
    SLA_SERVICE_URL: str = "http://sla-service:8003"
    NOTIFICATION_SERVICE_URL: str = "http://notification-service:8004"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
