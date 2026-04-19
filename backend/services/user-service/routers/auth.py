"""
Маршруты аутентификации для User Service
"""
import uuid
import secrets
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from shared import get_db, settings, hash_password, verify_password, create_access_token, create_refresh_token, decode_token
from shared.models import User, Role, PasswordResetToken
from schemas import UserLogin, Token, PasswordChange, UserResponse, ForgotPassword, ResetPassword

router = APIRouter()

# Схема получения токена из заголовка запроса
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Получение текущего пользователя из JWT-токена"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Не удалось проверить учетные данные",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    if not token:
        raise credentials_exception
    
    # Декодируем токен и проверяем его валидность
    payload = decode_token(token, settings.SECRET_KEY)
    if payload is None:
        raise credentials_exception
    
    user_id: str = payload.get("sub")
    if user_id is None:
        raise credentials_exception
    
    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise credentials_exception
    
    # Ищем пользователя в БД с подгрузкой роли и отдела
    result = await db.execute(
        select(User)
        .options(selectinload(User.role), selectinload(User.department))
        .where(User.id == user_uuid)
    )
    user = result.scalar_one_or_none()
    
    if user is None:
        raise credentials_exception
    
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Учетная запись отключена")
    
    return user


@router.post("/login", response_model=Token)
async def login(credentials: UserLogin, db: AsyncSession = Depends(get_db)):
    """Вход пользователя по email и паролю"""
    # Поиск пользователя с подгрузкой роли и отдела
    result = await db.execute(
        select(User)
        .options(selectinload(User.role), selectinload(User.department))
        .where(User.email == credentials.email)
    )
    user = result.scalar_one_or_none()
    
    # Проверка существования и пароля
    if not user or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Неверные учетные данные")
    
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Учетная запись отключена")
    
    # Генерация токенов доступа и обновления
    return Token(
        access_token=create_access_token(user.id, user.role.name, settings.SECRET_KEY),
        refresh_token=create_refresh_token(user.id, settings.SECRET_KEY)
    )


@router.post("/logout")
async def logout():
    """Выход из системы (заглушка, клиент должен удалить токен)"""
    return {"message": "Logged out"}


@router.post("/refresh", response_model=Token)
async def refresh(refresh_token: str, db: AsyncSession = Depends(get_db)):
    """Обновление пары токенов по refresh-токену"""
    # Проверяем валидность refresh-токена
    payload = decode_token(refresh_token, settings.SECRET_KEY)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Неверный токен")
    
    # Получаем пользователя из БД
    result = await db.execute(
        select(User)
        .options(selectinload(User.role))
        .where(User.id == uuid.UUID(payload["sub"]))
    )
    user = result.scalar_one_or_none()
    
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Пользователь не найден")
    
    # Выдаём новую пару токенов
    return Token(
        access_token=create_access_token(user.id, user.role.name, settings.SECRET_KEY),
        refresh_token=create_refresh_token(user.id, settings.SECRET_KEY)
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Получение данных текущего авторизованного пользователя"""
    return {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "role_id": current_user.role_id,
        "role_name": current_user.role.name if current_user.role else None,
        "department_id": current_user.department_id,
        "department_name": current_user.department.name if current_user.department else None,
        "phone": current_user.phone,
        "avatar": current_user.avatar,
        "is_active": current_user.is_active,
        "created_at": current_user.created_at
    }


@router.put("/password")
async def change_password(
    data: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Смена пароля текущим пользователем"""
    # Проверка текущего пароля
    if not verify_password(data.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Неверный текущий пароль")
    
    # Хэширование и сохранение нового пароля
    current_user.password_hash = hash_password(data.new_password)
    await db.commit()
    
    # Отправка уведомления о смене пароля
    import httpx
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                "http://notification-service:8004/email/send-templated",
                json={
                    "to": current_user.email,
                    "email_type": "password_changed",
                    "incident": {},
                    "extra": {"user_name": current_user.full_name},
                    "base_url": getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')
                }
            )
    except Exception as e:
        # Ошибка отправки письма не должна прерывать смену пароля
        pass
    
    return {"message": "Password changed"}


@router.post("/forgot-password")
async def forgot_password(data: ForgotPassword, db: AsyncSession = Depends(get_db)):
    """Отправка письма для сброса пароля"""
    # Поиск пользователя по email
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()
    
    # Возврат успеха для скрытия наличия email
    if not user:
        return {"message": "Если email существует, письмо отправлено"}
    
    # Аннулирование старых токенов
    old_tokens = await db.execute(
        select(PasswordResetToken).where(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used == False
        )
    )
    for token in old_tokens.scalars().all():
        token.used = True
    
    # Генерация нового токена
    token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(hours=1)
    
    reset_token = PasswordResetToken(
        user_id=user.id,
        token=token,
        expires_at=expires_at
    )
    db.add(reset_token)
    await db.commit()
    
    # Отправка email
    frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')
    reset_link = f"{frontend_url}/reset-password?token={token}"
    
    import httpx
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(
                "http://notification-service:8004/email/send",
                json={
                    "to": user.email,
                    "subject": "Сброс пароля",
                    "body": f"Для сброса пароля перейдите по ссылке: {reset_link}\n\nСсылка действительна 1 час.",
                    "html_body": f"""
                    <html>
                    <body style="font-family: Arial, sans-serif; padding: 20px;">
                        <h2>Сброс пароля</h2>
                        <p>Здравствуйте, {user.full_name}!</p>
                        <p>Вы запросили сброс пароля. Для установки нового пароля перейдите по ссылке:</p>
                        <p><a href="{reset_link}" style="background: #3b82f6; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Сбросить пароль</a></p>
                        <p>Или скопируйте ссылку: {reset_link}</p>
                        <p style="color: #666;">Ссылка действительна 1 час.</p>
                        <p style="color: #999; font-size: 12px;">Если вы не запрашивали сброс пароля, проигнорируйте это письмо.</p>
                    </body>
                    </html>
                    """
                }
            )
    except Exception as e:
        # Логирование без раскрытия ошибки
        pass
    
    return {"message": "Если email существует, письмо отправлено"}


@router.post("/reset-password")
async def reset_password(data: ResetPassword, db: AsyncSession = Depends(get_db)):
    """Сброс пароля по токену"""
    # Поиск действительного токена
    result = await db.execute(
        select(PasswordResetToken).where(
            PasswordResetToken.token == data.token,
            PasswordResetToken.used == False,
            PasswordResetToken.expires_at > datetime.utcnow()
        )
    )
    reset_token = result.scalar_one_or_none()
    
    if not reset_token:
        raise HTTPException(status_code=400, detail="Недействительная или истёкшая ссылка")
    
    # Получение пользователя
    user_result = await db.execute(select(User).where(User.id == reset_token.user_id))
    user = user_result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=400, detail="Пользователь не найден")
    
    # Обновление пароля
    user.password_hash = hash_password(data.new_password)
    reset_token.used = True
    await db.commit()
    
    return {"message": "Пароль успешно изменён"}