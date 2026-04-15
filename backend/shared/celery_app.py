"""
Celery configuration for background tasks
"""
from celery import Celery
from celery.schedules import crontab

from shared.config import settings

celery_app = Celery(
    "incident_management",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["shared.tasks"]
)

# Celery configuration
celery_app.conf.update(
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Europe/Moscow",
    enable_utc=True,
    
    # Result backend settings
    result_expires=3600,  # 1 hour
    
    # Task routing
    task_routes={
        "shared.tasks.check_sla_overdue": {"queue": "sla"},
        "shared.tasks.check_escalation": {"queue": "sla"},
        "shared.tasks.send_notification": {"queue": "notifications"},
    },
    
    # Beat schedule for periodic tasks
    beat_schedule={
        # Check SLA overdue every 5 minutes
        "check-sla-overdue": {
            "task": "shared.tasks.check_sla_overdue",
            "schedule": 300.0,  # 5 minutes
        },
        # Check escalation every 5 minutes
        "check-escalation": {
            "task": "shared.tasks.check_escalation",
            "schedule": 300.0,  # 5 minutes
        },
    },
)
