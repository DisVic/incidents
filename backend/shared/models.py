"""
ORM-модели данных для всех микросервисов.

Используется SQLAlchemy 2.0 с декларативным стилем.
Все модели наследуются от Base и используют UUID в качестве первичного ключа.

Структура:
- Базовые примеси (UUIDMixin, TimestampMixin)
- User Service: Role, Department, User, NotificationSettings
- Incident Service: Category, Priority, Status, Incident, IncidentHistory, Comment, Attachment
- SLA Service: SLAPolicy, EscalationRule
- Notification Service: Notification, PasswordResetToken
- Связи между моделями (relationships)
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, Boolean, Integer, DateTime, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base

Base = declarative_base()


# === БАЗОВЫЕ ПРИМЕСИ (MIXINS) ===
# Переиспользуемые наборы полей для моделей

class TimestampMixin:
    """Добавляет поля created_at и updated_at для отслеживания времени создания/изменения."""
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=True)


class UUIDMixin:
    """Добавляет UUID в качестве первичного ключа."""
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


# =============================================================================
# USER SERVICE — пользователи, роли, отделы
# =============================================================================

class Role(Base, UUIDMixin):
    """
    Роли пользователей: Admin, Manager, Executor, User.
    
    Определяют права доступа и функциональность в системе.
    """
    __tablename__ = "roles"
    
    name = Column(String(50), unique=True, nullable=False)
    description = Column(Text, nullable=True)


class Department(Base, UUIDMixin, TimestampMixin):
    """
    Отделы организации (IT, HR, Поддержка и т.д.).
    
    Используются для:
    - Группировки пользователей
    - Назначения инцидентов отделу-исполнителю
    - Фильтрации в отчётах
    """
    __tablename__ = "departments"
    
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    manager_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)  # Руководитель отдела


class User(Base, UUIDMixin, TimestampMixin):
    """
    Пользователи системы.
    
    Основные поля:
    - email/password_hash — аутентификация
    - role_id — права доступа
    - department_id — принадлежность к отделу
    - is_active — блокировка учётной записи
    """
    __tablename__ = "users"
    
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    role_id = Column(UUID(as_uuid=True), ForeignKey("roles.id"), nullable=False)
    department_id = Column(UUID(as_uuid=True), ForeignKey("departments.id"), nullable=True)  # null для Admin
    phone = Column(String(20), nullable=True)
    avatar = Column(Text, nullable=True)  # Base64 или URL
    is_active = Column(Boolean, default=True)  # False = заблокирован
    
    # Relationships — настраиваются в конце файла
    role = None
    department = None


class NotificationSettings(Base, UUIDMixin):
    """
    Настройки уведомлений для каждого пользователя.
    
    Каждое поле — JSON {"internal": bool, "email": bool}:
    - internal: показывать в интерфейсе (колокольчик)
    - email: отправлять на email
    
    Типы событий: incident_created, assigned_executor, new_comment, status_changed,
    incident_resolved, overdue, escalation, priority_changed.
    """
    __tablename__ = "notification_settings"
    
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), unique=True, nullable=False)
    # Каждое поле = {"internal": True/False, "email": True/False}
    incident_created = Column(JSON, default={"internal": True, "email": True})
    assigned_executor = Column(JSON, default={"internal": True, "email": True})
    new_comment = Column(JSON, default={"internal": True, "email": True})
    status_changed = Column(JSON, default={"internal": True, "email": True})
    incident_resolved = Column(JSON, default={"internal": True, "email": True})
    overdue = Column(JSON, default={"internal": True, "email": True})
    escalation = Column(JSON, default={"internal": True, "email": True})
    priority_changed = Column(JSON, default={"internal": True, "email": True})


# =============================================================================
# INCIDENT SERVICE — инциденты и справочники
# =============================================================================

class Category(Base, UUIDMixin):
    """
    Категории инцидентов для классификации заявок.
    
    Примеры: "Техническая проблема", "Доступ и учётные записи", "Сеть и связь".
    is_active: False = категория скрыта из интерфейса (не удаляется для истории).
    """
    __tablename__ = "categories"
    
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)


class Priority(Base, UUIDMixin):
    """
    Приоритеты инцидентов: Низкий, Средний, Высокий, Критический.
    
    level: числовой уровень для сортировки (1=Низкий, 4=Критический).
    color: hex-цвет для индикации в UI.
    """
    __tablename__ = "priorities"
    
    name = Column(String(50), nullable=False)
    level = Column(Integer, nullable=False)  # Для сортировки: 1=Низкий, 4=Критический
    color = Column(String(7), nullable=True)  # Hex цвет для UI


class Status(Base, UUIDMixin):
    """
    Статусы жизненного цикла инцидента.
    
    Стандартный поток: Новый → Назначен → В работе → Решён → Закрыт.
    color: hex-цвет для индикации в UI.
    """
    __tablename__ = "statuses"
    
    name = Column(String(50), nullable=False)
    color = Column(String(7), nullable=True)  # Hex цвет для UI


class Incident(Base, UUIDMixin, TimestampMixin):
    """
    Инцидент — основная сущность системы (заявка/тикет).
    
    Связи:
    - category_id: категория инцидента
    - priority_id: приоритет
    - status_id: текущий статус
    - department_id: отдел-исполнитель
    - initiator_id: кто создал
    - executor_id: кто решает
    
    SLA:
    - sla_deadline: дедлайн решения
    - overdue: текущая просрочка (сбрасывается при продлении)
    - was_overdue: фиксированная просрочка для статистики
    
    Временные метки этапов:
    - assigned_at: назначен исполнитель
    - in_progress_at: взят в работу
    - resolved_at: решён
    - closed_at: закрыт
    """
    __tablename__ = "incidents"
    
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    category_id = Column(UUID(as_uuid=True), ForeignKey("categories.id"), nullable=True)
    priority_id = Column(UUID(as_uuid=True), ForeignKey("priorities.id"), nullable=False)
    status_id = Column(UUID(as_uuid=True), ForeignKey("statuses.id"), nullable=False)
    department_id = Column(UUID(as_uuid=True), ForeignKey("departments.id"), nullable=False)  # Отдел-исполнитель
    initiator_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)  # Кто создал
    executor_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)  # Кто решает
    sla_deadline = Column(DateTime, nullable=False)  # Дедлайн по SLA
    overdue = Column(Boolean, default=False)  # Текущая просрочка (сбрасывается при продлении дедлайна)
    was_overdue = Column(Boolean, default=False)  # Замороженная просрочка для статистики (фиксируется при resolve/close)
    # Timestamps для разных этапов
    assigned_at = Column(DateTime, nullable=True)  # Когда назначен исполнитель
    in_progress_at = Column(DateTime, nullable=True)  # Когда взят в работу
    resolved_at = Column(DateTime, nullable=True)  # Когда решён
    closed_at = Column(DateTime, nullable=True)  # Когда закрыт


class IncidentHistory(Base, UUIDMixin):
    """
    История изменений инцидента (таймлайн/аудит-лог).
    
    Записывается при:
    - Смене статуса
    - Назначении исполнителя
    - Изменении приоритета/дедлайна
    - Системных событиях (просрочка, эскалация)
    
    user_id = None: системное действие (автоматическая просрочка и т.п.)
    """
    __tablename__ = "incident_history"
    
    incident_id = Column(UUID(as_uuid=True), ForeignKey("incidents.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), nullable=True)  # None = системное действие
    previous_status_id = Column(UUID(as_uuid=True), nullable=True)
    new_status_id = Column(UUID(as_uuid=True), nullable=True)
    comment = Column(Text, nullable=True)  # Описание действия
    created_at = Column(DateTime, default=datetime.utcnow)


class Comment(Base, UUIDMixin, TimestampMixin):
    """
    Комментарии к инциденту.
    
    Используются для обсуждения инцидента между участниками.
    Каждый комментарий имеет автора и временную метку.
    """
    __tablename__ = "comments"
    
    incident_id = Column(UUID(as_uuid=True), ForeignKey("incidents.id"), nullable=False)
    author_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=False)


class Attachment(Base, UUIDMixin):
    """
    Прикреплённые файлы к комментариям.
    
    Хранит метаданные файла (имя, путь, размер, MIME-тип).
    Файлы сохраняются на диск, в БД только информация о них.
    """
    __tablename__ = "attachments"
    
    incident_id = Column(UUID(as_uuid=True), ForeignKey("incidents.id"), nullable=False)
    uploader_id = Column(UUID(as_uuid=True), nullable=False)
    filename = Column(String(255), nullable=False)
    filepath = Column(String(500), nullable=False)
    filesize = Column(Integer, nullable=False)
    mime_type = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# =============================================================================
# SLA SERVICE — политики и эскалация
# =============================================================================

class SLAPolicy(Base, UUIDMixin):
    """
    SLA-политика: время на решение для каждого приоритета.
    
    resolution_hours: количество рабочих часов на решение инцидента.
    Пример: приоритет "Высокий" → 16 рабочих часов (2 дня).
    """
    __tablename__ = "sla_policies"
    
    priority_id = Column(UUID(as_uuid=True), ForeignKey("priorities.id"), unique=True, nullable=False)
    resolution_hours = Column(Integer, nullable=False)  # Рабочих часов на решение
    description = Column(Text, nullable=True)


class EscalationRule(Base, UUIDMixin):
    """
    Правила эскалации: кому и когда отправлять уведомления о проблемах.
    
    level: уровень эскалации (1 = предупреждение, 2 = критично).
    condition_type: условие срабатывания ("percent_80" или "overdue").
    notify_role_id: роль получателя уведомления (Manager/Admin).
    """
    __tablename__ = "escalation_rules"
    
    level = Column(Integer, nullable=False)  # 1 = 80% SLA, 2 = просрочка
    notify_role_id = Column(UUID(as_uuid=True), ForeignKey("roles.id"), nullable=False)  # Кого уведомлять
    condition_type = Column(String(50), nullable=False)  # percent_80 или overdue
    is_active = Column(Boolean, default=True)


# =============================================================================
# NOTIFICATION SERVICE — уведомления
# =============================================================================

class Notification(Base, UUIDMixin):
    """
    Внутренние уведомления (колокольчик в интерфейсе).
    
    type: тип события (incident_created, status_changed, overdue, escalation и т.д.).
    is_read: прочитано пользователем или нет.
    """
    __tablename__ = "notifications"
    
    user_id = Column(UUID(as_uuid=True), nullable=False)
    incident_id = Column(UUID(as_uuid=True), nullable=True)
    type = Column(String(50), nullable=False)  # incident_created, status_changed, overdue, escalation, etc.
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=True)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class PasswordResetToken(Base, UUIDMixin):
    """
    Токены для сброса пароля через email.
    
    Генерируется при запросе "Забыли пароль?", отправляется ссылкой на почту.
    Время жизни: 1 час. После использования помечается как used=True.
    """
    __tablename__ = "password_reset_tokens"
    
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    token = Column(String(255), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)  # Время истечения (1 час)
    used = Column(Boolean, default=False)  # True = токен уже использован
    created_at = Column(DateTime, default=datetime.utcnow)


# =============================================================================
# RELATIONSHIPS — связи между моделями (настраиваются после объявления всех классов)
# =============================================================================
from sqlalchemy.orm import relationship

# User relationships
User.role = relationship("Role", backref="users")
User.department = relationship("Department", foreign_keys=[User.department_id], backref="users")
Department.manager = relationship("User", foreign_keys=[Department.manager_id], backref="managed_departments")

# Incident relationships
Incident.status = relationship("Status", backref="incidents")
Incident.priority = relationship("Priority", backref="incidents")
Incident.category = relationship("Category", backref="incidents")
Incident.department = relationship("Department", foreign_keys=[Incident.department_id], backref="incidents")
Incident.initiator = relationship("User", foreign_keys=[Incident.initiator_id], backref="created_incidents")
Incident.executor = relationship("User", foreign_keys=[Incident.executor_id], backref="assigned_incidents")

# Comment relationships
Comment.author = relationship("User", foreign_keys=[Comment.author_id], backref="comments")
Comment.incident = relationship("Incident", backref="comments")

# Attachment relationships
Attachment.incident = relationship("Incident", backref="attachments")

# IncidentHistory relationships
IncidentHistory.incident = relationship("Incident", backref="history")

# SLAPolicy relationships
SLAPolicy.priority = relationship("Priority", backref="sla_policy")