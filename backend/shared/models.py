"""Модели данных для всех микросервисов"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, Boolean, Integer, DateTime, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class TimestampMixin:
    """Добавляет поля created_at и updated_at ко всем моделям"""
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=True)


class UUIDMixin:
    """Добавляет первичный ключ UUID ко всем моделям"""
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


# === Модели сервиса пользователей ===

class Role(Base, UUIDMixin):
    """Роль пользователя (Admin, Manager, Executor)"""
    __tablename__ = "roles"
    
    name = Column(String(50), unique=True, nullable=False)
    description = Column(Text, nullable=True)


class Department(Base, UUIDMixin, TimestampMixin):
    """Отдел организации"""
    __tablename__ = "departments"
    
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    manager_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)


class User(Base, UUIDMixin, TimestampMixin):
    """Пользователь системы"""
    __tablename__ = "users"
    
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    role_id = Column(UUID(as_uuid=True), ForeignKey("roles.id"), nullable=False)
    department_id = Column(UUID(as_uuid=True), ForeignKey("departments.id"), nullable=True)
    phone = Column(String(20), nullable=True)
    avatar = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    
    # Связи с другими моделями
    role = None
    department = None


class NotificationSettings(Base, UUIDMixin):
    """Настройки уведомлений пользователя"""
    __tablename__ = "notification_settings"
    
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), unique=True, nullable=False)
    incident_created = Column(JSON, default={"internal": True, "email": True})
    assigned_executor = Column(JSON, default={"internal": True, "email": True})
    new_comment = Column(JSON, default={"internal": True, "email": True})
    status_changed = Column(JSON, default={"internal": True, "email": True})
    incident_resolved = Column(JSON, default={"internal": True, "email": True})
    overdue = Column(JSON, default={"internal": True, "email": True})
    escalation = Column(JSON, default={"internal": True, "email": True})
    priority_changed = Column(JSON, default={"internal": True, "email": True})


# === Модели сервиса инцидентов ===

class Category(Base, UUIDMixin):
    """Категория инцидента"""
    __tablename__ = "categories"
    
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)


class Priority(Base, UUIDMixin):
    """Приоритет инцидента"""
    __tablename__ = "priorities"
    
    name = Column(String(50), nullable=False)
    level = Column(Integer, nullable=False)
    color = Column(String(7), nullable=True)


class Status(Base, UUIDMixin):
    """Статус инцидента"""
    __tablename__ = "statuses"
    
    name = Column(String(50), nullable=False)
    color = Column(String(7), nullable=True)


class Incident(Base, UUIDMixin, TimestampMixin):
    """Инцидент — основная сущность системы"""
    __tablename__ = "incidents"
    
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    category_id = Column(UUID(as_uuid=True), ForeignKey("categories.id"), nullable=True)
    priority_id = Column(UUID(as_uuid=True), ForeignKey("priorities.id"), nullable=False)
    status_id = Column(UUID(as_uuid=True), ForeignKey("statuses.id"), nullable=False)
    department_id = Column(UUID(as_uuid=True), ForeignKey("departments.id"), nullable=False)
    initiator_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    executor_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    sla_deadline = Column(DateTime, nullable=False)  # Дедлайн по SLA
    overdue = Column(Boolean, default=False)  # Просрочен ли сейчас
    was_overdue = Column(Boolean, default=False)  # Был ли просрочен в прошлом
    assigned_at = Column(DateTime, nullable=True)  # Время назначения
    in_progress_at = Column(DateTime, nullable=True)  # Время начала работы
    resolved_at = Column(DateTime, nullable=True)  # Время решения
    closed_at = Column(DateTime, nullable=True)  # Время закрытия


class IncidentHistory(Base, UUIDMixin):
    """История изменений инцидента"""
    __tablename__ = "incident_history"
    
    incident_id = Column(UUID(as_uuid=True), ForeignKey("incidents.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), nullable=True)
    previous_status_id = Column(UUID(as_uuid=True), nullable=True)
    new_status_id = Column(UUID(as_uuid=True), nullable=True)
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Comment(Base, UUIDMixin, TimestampMixin):
    """Комментарий к инциденту"""
    __tablename__ = "comments"
    
    incident_id = Column(UUID(as_uuid=True), ForeignKey("incidents.id"), nullable=False)
    author_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=False)


class Attachment(Base, UUIDMixin):
    """Вложение к инциденту"""
    __tablename__ = "attachments"
    
    incident_id = Column(UUID(as_uuid=True), ForeignKey("incidents.id"), nullable=False)
    uploader_id = Column(UUID(as_uuid=True), nullable=False)
    filename = Column(String(255), nullable=False)
    filepath = Column(String(500), nullable=False)
    filesize = Column(Integer, nullable=False)
    mime_type = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# === Модели сервиса SLA ===

class SLAPolicy(Base, UUIDMixin):
    """SLA-политика для приоритета"""
    __tablename__ = "sla_policies"
    
    priority_id = Column(UUID(as_uuid=True), ForeignKey("priorities.id"), unique=True, nullable=False)
    resolution_hours = Column(Integer, nullable=False)  # Время на решение в часах
    description = Column(Text, nullable=True)


class EscalationRule(Base, UUIDMixin):
    """Правило эскалации"""
    __tablename__ = "escalation_rules"
    
    level = Column(Integer, nullable=False)  # Уровень эскалации (1, 2...)
    notify_role_id = Column(UUID(as_uuid=True), ForeignKey("roles.id"), nullable=False)
    condition_type = Column(String(50), nullable=False)  # Условие срабатывания
    is_active = Column(Boolean, default=True)


# === Модели сервиса уведомлений ===

class Notification(Base, UUIDMixin):
    """Внутреннее уведомление пользователя"""
    __tablename__ = "notifications"
    
    user_id = Column(UUID(as_uuid=True), nullable=False)
    incident_id = Column(UUID(as_uuid=True), nullable=True)
    type = Column(String(50), nullable=False)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=True)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class PasswordResetToken(Base, UUIDMixin):
    """Токен сброса пароля"""
    __tablename__ = "password_reset_tokens"
    
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    token = Column(String(255), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


# === Связи между моделями ===
from sqlalchemy.orm import relationship

User.role = relationship("Role", backref="users")
User.department = relationship("Department", foreign_keys=[User.department_id], backref="users")
Department.manager = relationship("User", foreign_keys=[Department.manager_id], backref="managed_departments")

Incident.status = relationship("Status", backref="incidents")
Incident.priority = relationship("Priority", backref="incidents")
Incident.category = relationship("Category", backref="incidents")
Incident.department = relationship("Department", foreign_keys=[Incident.department_id], backref="incidents")
Incident.initiator = relationship("User", foreign_keys=[Incident.initiator_id], backref="created_incidents")
Incident.executor = relationship("User", foreign_keys=[Incident.executor_id], backref="assigned_incidents")

Comment.author = relationship("User", foreign_keys=[Comment.author_id], backref="comments")
Comment.incident = relationship("Incident", backref="comments")

Attachment.incident = relationship("Incident", backref="attachments")

IncidentHistory.incident = relationship("Incident", backref="history")

SLAPolicy.priority = relationship("Priority", backref="sla_policy")
