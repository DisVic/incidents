"""
Shared models and base classes for all microservices
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, Boolean, Integer, DateTime, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base

Base = declarative_base()


# ============================================
# SHARED BASE CLASSES
# ============================================

class TimestampMixin:
    """Mixin for created_at and updated_at timestamps"""
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=True)


class UUIDMixin:
    """Mixin for UUID primary key"""
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


# ============================================
# USER SERVICE MODELS
# ============================================

class Role(Base, UUIDMixin):
    __tablename__ = "roles"
    
    name = Column(String(50), unique=True, nullable=False)
    description = Column(Text, nullable=True)


class Department(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "departments"
    
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    manager_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)


class User(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "users"
    
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    role_id = Column(UUID(as_uuid=True), ForeignKey("roles.id"), nullable=False)
    department_id = Column(UUID(as_uuid=True), ForeignKey("departments.id"), nullable=True)
    phone = Column(String(20), nullable=True)
    avatar = Column(Text, nullable=True)  # Base64 encoded image or URL
    is_active = Column(Boolean, default=True)
    
    # Relationships
    role = None  # Will be set after Role class
    department = None  # Will be set after Department class


class NotificationSettings(Base, UUIDMixin):
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


# ============================================
# INCIDENT SERVICE MODELS
# ============================================

class Category(Base, UUIDMixin):
    __tablename__ = "categories"
    
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)


class Priority(Base, UUIDMixin):
    __tablename__ = "priorities"
    
    name = Column(String(50), nullable=False)
    level = Column(Integer, nullable=False)
    color = Column(String(7), nullable=True)


class Status(Base, UUIDMixin):
    __tablename__ = "statuses"
    
    name = Column(String(50), nullable=False)
    color = Column(String(7), nullable=True)


class Incident(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "incidents"
    
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    category_id = Column(UUID(as_uuid=True), ForeignKey("categories.id"), nullable=True)
    priority_id = Column(UUID(as_uuid=True), ForeignKey("priorities.id"), nullable=False)
    status_id = Column(UUID(as_uuid=True), ForeignKey("statuses.id"), nullable=False)
    department_id = Column(UUID(as_uuid=True), ForeignKey("departments.id"), nullable=False)
    initiator_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    executor_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    sla_deadline = Column(DateTime, nullable=False)
    overdue = Column(Boolean, default=False)
    was_overdue = Column(Boolean, default=False)  # Frozen at resolve/close time for statistics
    assigned_at = Column(DateTime, nullable=True)
    in_progress_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=True)


class IncidentHistory(Base, UUIDMixin):
    __tablename__ = "incident_history"
    
    incident_id = Column(UUID(as_uuid=True), ForeignKey("incidents.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), nullable=True)
    previous_status_id = Column(UUID(as_uuid=True), nullable=True)
    new_status_id = Column(UUID(as_uuid=True), nullable=True)
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Comment(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "comments"
    
    incident_id = Column(UUID(as_uuid=True), ForeignKey("incidents.id"), nullable=False)
    author_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=False)


class Attachment(Base, UUIDMixin):
    __tablename__ = "attachments"
    
    incident_id = Column(UUID(as_uuid=True), ForeignKey("incidents.id"), nullable=False)
    uploader_id = Column(UUID(as_uuid=True), nullable=False)
    filename = Column(String(255), nullable=False)
    filepath = Column(String(500), nullable=False)
    filesize = Column(Integer, nullable=False)
    mime_type = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# ============================================
# SLA SERVICE MODELS
# ============================================

class SLAPolicy(Base, UUIDMixin):
    __tablename__ = "sla_policies"
    
    priority_id = Column(UUID(as_uuid=True), ForeignKey("priorities.id"), unique=True, nullable=False)
    resolution_hours = Column(Integer, nullable=False)
    description = Column(Text, nullable=True)


class EscalationRule(Base, UUIDMixin):
    __tablename__ = "escalation_rules"
    
    level = Column(Integer, nullable=False)
    notify_role_id = Column(UUID(as_uuid=True), ForeignKey("roles.id"), nullable=False)
    condition_type = Column(String(50), nullable=False)
    is_active = Column(Boolean, default=True)


# ============================================
# NOTIFICATION SERVICE MODELS
# ============================================

class Notification(Base, UUIDMixin):
    __tablename__ = "notifications"
    
    user_id = Column(UUID(as_uuid=True), nullable=False)
    incident_id = Column(UUID(as_uuid=True), nullable=True)
    type = Column(String(50), nullable=False)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=True)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class PasswordResetToken(Base, UUIDMixin):
    __tablename__ = "password_reset_tokens"
    
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    token = Column(String(255), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


# ============================================
# RELATIONSHIPS
# ============================================
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
