"""Настройка Celery для фоновых задач"""
from celery import Celery
from celery.schedules import crontab

from shared.config import settings


# Основной экземпляр Celery для всех фоновых задач
celery_app = Celery(
    "incident_management",
    broker=settings.REDIS_URL,  # Брокер сообщений (Redis)
    backend=settings.REDIS_URL,  # Хранение результатов задач
    include=["shared.tasks"]  # Модуль с задачами
)

# Конфигурация Celery
celery_app.conf.update(
    task_serializer="json",  # Сериализация задач в JSON
    accept_content=["json"],  # Принимаем только JSON
    result_serializer="json",  # Результаты в JSON
    timezone="Europe/Moscow",  # Часовой пояс
    enable_utc=True,  # Использовать UTC
    
    result_expires=3600,  # Результаты хранятся 1 час
    
    # Распределение задач по очередям
    task_routes={
        "shared.tasks.check_sla_overdue": {"queue": "sla"},
        "shared.tasks.check_escalation": {"queue": "sla"},
        "shared.tasks.send_notification": {"queue": "notifications"},
    },
    
    # Периодические задачи (запускаются каждые 5 минут)
    beat_schedule={
        "check-sla-overdue": {
            "task": "shared.tasks.check_sla_overdue",
            "schedule": 300.0,
        },
        "check-escalation": {
            "task": "shared.tasks.check_escalation",
            "schedule": 300.0,
        },
    },
)
