"""
Pydantic schemas for User Service
"""
import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, field_validator


class UserLogin(BaseModel):
    """Данные для входа пользователя"""
    email: EmailStr
    password: str


class Token(BaseModel):
    """JWT токены доступа"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class PasswordChange(BaseModel):
    """Запрос на смену пароля"""
    current_password: str
    new_password: str = Field(..., min_length=8)


class ForgotPassword(BaseModel):
    """Запрос на восстановление пароля"""
    email: EmailStr


class ResetPassword(BaseModel):
    """Запрос на сброс пароля по токену"""
    token: str
    new_password: str = Field(..., min_length=8)


class UserBase(BaseModel):
    """Базовые поля пользователя"""
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
    """Данные для создания пользователя"""
    password: str = Field(..., min_length=8, description="Пароль (минимум 8 символов)")
    
    @field_validator('password')
    @classmethod
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Пароль должен содержать минимум 8 символов')
        return v


class UserUpdate(BaseModel):
    """Поля для обновления пользователя"""
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
    """Данные пользователя для ответа"""
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
        from_attributes = True


class DepartmentBase(BaseModel):
    """Базовые поля отдела"""
    name: str
    description: Optional[str] = None
    manager_id: Optional[uuid.UUID] = None


class DepartmentCreate(DepartmentBase):
    """Данные для создания отдела"""
    pass


class DepartmentUpdate(BaseModel):
    """Поля для обновления отдела"""
    name: Optional[str] = None
    description: Optional[str] = None
    manager_id: Optional[uuid.UUID] = None


class DepartmentResponse(BaseModel):
    """Данные отдела для ответа"""
    id: uuid.UUID
    name: str
    description: Optional[str]
    manager_id: Optional[uuid.UUID]
    created_at: datetime
    
    class Config:
        from_attributes = True
