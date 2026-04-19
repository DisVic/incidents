"""
Настройка Celery для фоновых задач.

Celery используется для:
- Мониторинга SLA (проверка просрочек каждые 5 минут)
- Эскалации инцидентов
- Отправки email-уведомлений
- Асинхронных уведомлений пользователей

Задачи планируются через Celery Beat и выполняются воркерами.
"""
from celery import Celery
from celery.schedules import crontab

from shared.config import settings

celery_app = Celery(
    "incident_management",
    broker=settings.REDIS_URL,      # Redis как брокер сообщений
    backend=settings.REDIS_URL,     # Redis как хранилище результатов
    include=["shared.tasks"]        # Модуль с задачами
)

# Конфигурация Celery
celery_app.conf.update(
    # Сериализация задач и результатов
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Europe/Moscow",
    enable_utc=True,
    
    # Хранение результатов задач (1 час)
    result_expires=3600,
    
    # Маршрутизация задач по очередям
    task_routes={
        "shared.tasks.check_sla_overdue": {"queue": "sla"},
        "shared.tasks.check_escalation": {"queue": "sla"},
        "shared.tasks.send_notification": {"queue": "notifications"},
    },
    
    # Расписание периодических задач (Celery Beat)
    beat_schedule={
        # Проверка просрочек SLA каждые 5 минут
        "check-sla-overdue": {
            "task": "shared.tasks.check_sla_overdue",
            "schedule": 300.0,
        },
        # Проверка эскалации каждые 5 минут
        "check-escalation": {
            "task": "shared.tasks.check_escalation",
            "schedule": 300.0,
        },
    },
)
