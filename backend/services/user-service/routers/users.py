"""
API управления пользователями — CRUD, блокировка, аватары.

Endpoint'ы:
- GET /users — список пользователей (пагинация)
- GET /users/{id} — данные пользователя
- POST /users — создание пользователя
- PUT /users/{id} — обновление (включая блокировку)
- DELETE /users/{id} — удаление (нельзя последнего Admin)
- PUT /users/{id}/password — смена пароля администратором
- POST /users/{id}/avatar — загрузка аватара (Base64)
"""
import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from pydantic import BaseModel

from shared import get_db, hash_password, verify_password
from shared.models import User, Role, Department, NotificationSettings
from schemas import UserCreate, UserUpdate, UserResponse, PasswordChange

router = APIRouter()

# URL incident-service для межсервисных вызовов
INCIDENT_SERVICE_URL = "http://incident-service:8002"


async def reset_executor_incidents(user_id: str):
    """
    Сбрасывает назначенные инциденты пользователя при блокировке/удалении.
    
    Вызывает endpoint incident-service, который переводит инциденты
    в статус "Новый" и снимает исполнителя.
    """
    async with httpx.AsyncClient() as client:
        try:
            await client.post(f"{INCIDENT_SERVICE_URL}/incidents/reset-executor/{user_id}")
        except Exception as e:
            # Логируем ошибку, но не прерываем операцию
            print(f"Failed to reset executor incidents: {e}")


@router.get("")
async def list_users(
    page: int = 1, limit: int = 20,
    db: AsyncSession = Depends(get_db)
):
    """
    Список пользователей с пагинацией.
    
    Используется в админ-панели для управления пользователями.
    Возвращает данные с ролью и отделом, без password_hash.
    
    Query params:
    - page: номер страницы (default: 1)
    - limit: количество на странице (default: 20)
    """
    offset = (page - 1) * limit
    result = await db.execute(
        select(User)
        .options(selectinload(User.role), selectinload(User.department))
        .offset(offset)
        .limit(limit)
    )
    users = result.scalars().all()
    
    total = await db.execute(select(func.count()).select_from(User))
    
    # Исключаем password_hash из ответа
    users_data = [
        {
            "id": str(u.id),
            "email": u.email,
            "full_name": u.full_name,
            "role_id": str(u.role_id),
            "role_name": u.role.name if u.role else None,
            "department_id": str(u.department_id) if u.department_id else None,
            "department_name": u.department.name if u.department else None,
            "phone": u.phone,
            "avatar": u.avatar,
            "is_active": u.is_active,
            "created_at": u.created_at.isoformat() if u.created_at else None,
        }
        for u in users
    ]
    
    return {"data": users_data, "total": total.scalar(), "page": page, "limit": limit}


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: str, db: AsyncSession = Depends(get_db)):
    """Получение данных пользователя по ID."""
    result = await db.execute(
        select(User)
        .options(selectinload(User.role), selectinload(User.department))
        .where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role_id": user.role_id,
        "role_name": user.role.name if user.role else None,
        "department_id": user.department_id,
        "department_name": user.department.name if user.department else None,
        "phone": user.phone,
        "avatar": user.avatar,
        "is_active": user.is_active,
        "created_at": user.created_at
    }


@router.post("", response_model=UserResponse, status_code=201)
async def create_user(data: UserCreate, db: AsyncSession = Depends(get_db)):
    """
    Создание нового пользователя.
    
    - Хеширует пароль перед сохранением
    - Создаёт настройки уведомлений (все включены)
    - Проверяет уникальность email
    
    Raises:
        HTTPException 400: Email уже существует
    """
    # Проверка уникальности email
    existing = await db.execute(select(User).where(User.email == data.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email exists")
    
    user = User(
        email=data.email,
        password_hash=hash_password(data.password),
        full_name=data.full_name,
        role_id=data.role_id,
        department_id=data.department_id
    )
    db.add(user)
    await db.flush()  # Получаем user.id до коммита
    
    # Создаём настройки уведомлений
    all_enabled = {"internal": True, "email": True}
    notif_settings = NotificationSettings(
        user_id=user.id,
        incident_created=all_enabled,
        assigned_executor=all_enabled,
        new_comment=all_enabled,
        status_changed=all_enabled,
        incident_resolved=all_enabled,
        overdue=all_enabled,
        escalation=all_enabled,
        priority_changed=all_enabled
    )
    db.add(notif_settings)
    await db.commit()
    
    # Загружаем с relationships
    result = await db.execute(
        select(User)
        .options(selectinload(User.role), selectinload(User.department))
        .where(User.id == user.id)
    )
    user = result.scalar_one()
    
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role_id": user.role_id,
        "role_name": user.role.name if user.role else None,
        "department_id": user.department_id,
        "department_name": user.department.name if user.department else None,
        "phone": user.phone,
        "avatar": user.avatar,
        "is_active": user.is_active,
        "created_at": user.created_at
    }


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(user_id: str, data: UserUpdate, db: AsyncSession = Depends(get_db)):
    """
    Обновление данных пользователя.
    
    - При блокировке (is_active=False) сбрасывает назначенные инциденты
    - Обновляет только переданные поля
    """
    result = await db.execute(
        select(User)
        .options(selectinload(User.role), selectinload(User.department))
        .where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Проверяем, блокируется ли пользователь
    was_active = user.is_active
    will_be_blocked = data.is_active == False and was_active == True
    
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    
    await db.commit()
    
    # Сбрасываем инциденты при блокировке
    if will_be_blocked:
        await reset_executor_incidents(user_id)
    
    # Перезагружаем с relationships
    result = await db.execute(
        select(User)
        .options(selectinload(User.role), selectinload(User.department))
        .where(User.id == user_id)
    )
    user = result.scalar_one()
    
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role_id": user.role_id,
        "role_name": user.role.name if user.role else None,
        "department_id": user.department_id,
        "department_name": user.department.name if user.department else None,
        "phone": user.phone,
        "avatar": user.avatar,
        "is_active": user.is_active,
        "created_at": user.created_at
    }


@router.delete("/{user_id}")
async def delete_user(user_id: str, db: AsyncSession = Depends(get_db)):
    """
    Удаление пользователя.
    
    - Проверяет, что не последний Admin
    - Сбрасывает назначенные инциденты
    """
    result = await db.execute(
        select(User).options(selectinload(User.role)).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    # Нельзя удалить последнего администратора
    if user.role and user.role.name == "Admin":
        admin_count = await db.execute(
            select(func.count()).select_from(User).join(Role).where(Role.name == "Admin", User.is_active == True)
        )
        if admin_count.scalar() <= 1:
            raise HTTPException(status_code=400, detail="Нельзя удалить последнего администратора")
    
    # Сбрасываем инциденты перед удалением
    await reset_executor_incidents(user_id)
    
    await db.delete(user)
    await db.commit()
    
    return {"message": "Пользователь удалён"}


@router.put("/{user_id}/password")
async def change_password(user_id: str, data: PasswordChange, db: AsyncSession = Depends(get_db)):
    """
    Смена пароля пользователя (администратором).
    
    - Проверяет текущий пароль
    - Отправляет уведомление о смене пароля
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    # Проверяем текущий пароль
    if not verify_password(data.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Неверный текущий пароль")
    
    # Проверяем длину нового пароля
    if len(data.new_password) < 6:
        raise HTTPException(status_code=400, detail="Пароль должен быть не менее 6 символов")
    
    # Обновляем пароль
    user.password_hash = hash_password(data.new_password)
    await db.commit()
    
    # Отправляем уведомление
    from shared.tasks import send_notification
    send_notification.delay(
        str(user.id),
        None,
        "password_changed",
        "Пароль изменён",
        f"Ваш пароль был успешно изменён. Если это были не вы, немедленно свяжитесь с администратором."
    )
    
    return {"message": "Пароль изменён"}


class AvatarUpload(BaseModel):
    """Данные для загрузки аватара (Base64 или пустая строка для удаления)."""
    avatar: str = ""  # Base64 изображение или пустая строка для удаления


@router.post("/{user_id}/avatar")
async def upload_avatar(user_id: str, data: AvatarUpload, db: AsyncSession = Depends(get_db)):
    """
    Загрузка аватара пользователя.
    
    - Принимает Base64 изображение (макс. 500KB)
    - Пустая строка удаляет аватар
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    avatar_data = data.avatar
    
    # Проверка размера (Base64 ~33% больше бинарных данных)
    if avatar_data:
        if avatar_data.startswith('data:image/'):
            if len(avatar_data) > 700000:  # ~500KB в base64
                raise HTTPException(status_code=400, detail="Изображение слишком большое (максимум 500KB)")
        elif len(avatar_data) > 500000:
            raise HTTPException(status_code=400, detail="Изображение слишком большое")
    
    # Сохраняем None если пустая строка
    user.avatar = avatar_data if avatar_data else None
    await db.commit()
    
    return {"message": "Аватар обновлён", "avatar": user.avatar}