"""
Pydantic-схемы для User Service.

Схемы используются для:
- Валидации входных данных (request body)
- Сериализации ответов (response model)
- Документации API в Swagger UI

Разделы:
- Аутентификация: UserLogin, Token, PasswordChange, ForgotPassword, ResetPassword
- Пользователи: UserBase, UserCreate, UserUpdate, UserResponse
- Отделы: DepartmentBase, DepartmentCreate, DepartmentUpdate, DepartmentResponse
"""
import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, field_validator


# =============================================================================
# АУТЕНТИФИКАЦИЯ
# =============================================================================

class UserLogin(BaseModel):
    """Данные для входа (email + пароль)."""
    email: EmailStr
    password: str


class Token(BaseModel):
    """Ответ при успешной аутентификации — пара JWT-токенов."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class PasswordChange(BaseModel):
    """Смена пароля (текущий + новый)."""
    current_password: str
    new_password: str = Field(..., min_length=8)


class ForgotPassword(BaseModel):
    """Запрос сброса пароля (email)."""
    email: EmailStr


class ResetPassword(BaseModel):
    """Установка нового пароля по токену."""
    token: str
    new_password: str = Field(..., min_length=8)


# =============================================================================
# ПОЛЬЗОВАТЕЛИ
# =============================================================================

class UserBase(BaseModel):
    """Базовая схема пользователя (общие поля для создания/обновления)."""
    email: EmailStr = Field(..., description="Email адрес пользователя")
    full_name: str = Field(..., min_length=2, max_length=255, description="ФИО пользователя")
    role_id: uuid.UUID = Field(..., description="ID роли пользователя")
    department_id: Optional[uuid.UUID] = Field(None, description="ID отдела")
    phone: Optional[str] = Field(None, max_length=20)
    
    @field_validator('full_name')
    @classmethod
    def validate_full_name(cls, v):
        if not v or len(v.strip()) < 2:
            raise ValueError('ФИО должно содержать минимум 2 символа')
        return v.strip()


class UserCreate(UserBase):
    """Создание пользователя (требует пароль)."""
    password: str = Field(..., min_length=8, description="Пароль (минимум 8 символов)")
    
    @field_validator('password')
    @classmethod
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Пароль должен содержать минимум 8 символов')
        return v


class UserUpdate(BaseModel):
    """Обновление пользователя (все поля опциональны)."""
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(None, min_length=2, max_length=255)
    role_id: Optional[uuid.UUID] = None
    department_id: Optional[uuid.UUID] = None
    phone: Optional[str] = None
    avatar: Optional[str] = None
    is_active: Optional[bool] = None
    
    @field_validator('full_name')
    @classmethod
    def validate_full_name(cls, v):
        if v is not None and len(v.strip()) < 2:
            raise ValueError('ФИО должно содержать минимум 2 символа')
        return v.strip() if v else v


class UserResponse(BaseModel):
    """Ответ с данными пользователя (для GET запросов)."""
    id: uuid.UUID
    email: str
    full_name: str
    role_id: uuid.UUID
    role_name: Optional[str] = None
    department_id: Optional[uuid.UUID]
    department_name: Optional[str] = None
    phone: Optional[str]
    avatar: Optional[str] = None
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True  # Разрешает ORM-режим (загрузка из SQLAlchemy моделей)


# =============================================================================
# ОТДЕЛЫ
# =============================================================================

class DepartmentBase(BaseModel):
    """Базовая схема отдела."""
    name: str
    description: Optional[str] = None
    manager_id: Optional[uuid.UUID] = None


class DepartmentCreate(DepartmentBase):
    """Создание отдела."""
    pass


class DepartmentUpdate(BaseModel):
    """Обновление отдела (все поля опциональны)."""
    name: Optional[str] = None
    description: Optional[str] = None
    manager_id: Optional[uuid.UUID] = None


class DepartmentResponse(BaseModel):
    """Ответ с данными отдела."""
    id: uuid.UUID
    name: str
    description: Optional[str]
    manager_id: Optional[uuid.UUID]
    created_at: datetime
    
    class Config:
        from_attributes = True
