"""
API авторизации — вход, выход, сброс пароля, получение текущего пользователя.

Endpoint'ы:
- POST /auth/login — вход по email/паролю, получение JWT-токенов
- POST /auth/logout — выход (клиент удаляет токены)
- POST /auth/refresh — обновление access-токена
- GET /auth/me — данные текущего пользователя
- PUT /auth/password — смена пароля
- POST /auth/forgot-password — запрос сброса пароля
- POST /auth/reset-password — установка нового пароля по токену
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

# OAuth2 схема для извлечения токена из заголовка Authorization: Bearer <token>
# auto_error=False — позволяем вручную обрабатывать отсутствие токена
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Dependency для получения текущего пользователя из JWT-токена.
    
    Используется в защищённых endpoint'ах как Depends(get_current_user).
    Проверяет валидность токена, активность пользователя, загружает роль и отдел.
    
    Raises:
        HTTPException 401: Токен отсутствует или невалиден
        HTTPException 403: Учётная запись заблокирована (is_active=False)
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    if not token:
        raise credentials_exception
    
    # Декодируем JWT и извлекаем user_id
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
    
    # Загружаем пользователя с ролью и отделом
    result = await db.execute(
        select(User)
        .options(selectinload(User.role), selectinload(User.department))
        .where(User.id == user_uuid)
    )
    user = result.scalar_one_or_none()
    
    if user is None:
        raise credentials_exception
    
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")
    
    return user


@router.post("/login", response_model=Token)
async def login(credentials: UserLogin, db: AsyncSession = Depends(get_db)):
    """
    Вход в систему по email и паролю.
    
    Проверяет учётные данные, возвращает пару токенов:
    - access_token: для API-запросов (живёт 30 минут)
    - refresh_token: для обновления access-токена (живёт 7 дней)
    
    Raises:
        HTTPException 401: Неверный email или пароль
        HTTPException 403: Учётная запись заблокирована
    """
    result = await db.execute(
        select(User)
        .options(selectinload(User.role), selectinload(User.department))
        .where(User.email == credentials.email)
    )
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")
    
    return Token(
        access_token=create_access_token(user.id, user.role.name, settings.SECRET_KEY),
        refresh_token=create_refresh_token(user.id, settings.SECRET_KEY)
    )


@router.post("/logout")
async def logout():
    """
    Выход из системы.
    
    Фактически не делает ничего на сервере — клиент удаляет токены.
    В будущих версиях можно добавить blacklist для токенов.
    """
    return {"message": "Logged out"}


@router.post("/refresh", response_model=Token)
async def refresh(refresh_token: str, db: AsyncSession = Depends(get_db)):
    """
    Обновление access-токена по refresh-токену.
    
    Используется когда access-токен истёк (через 30 минут).
    Проверяет валидность refresh-токена и возвращает новую пару.
    
    Raises:
        HTTPException 401: Невалидный токен или пользователь не найден
    """
    # Декодируем refresh-токен и проверяем тип
    payload = decode_token(refresh_token, settings.SECRET_KEY)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid token")
    
    result = await db.execute(
        select(User)
        .options(selectinload(User.role))
        .where(User.id == uuid.UUID(payload["sub"]))
    )
    user = result.scalar_one_or_none()
    
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found")
    
    return Token(
        access_token=create_access_token(user.id, user.role.name, settings.SECRET_KEY),
        refresh_token=create_refresh_token(user.id, settings.SECRET_KEY)
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """
    Получение данных текущего пользователя.
    
    Используется для отображения профиля в интерфейсе.
    Возвращает всю информацию о пользователе включая роль и отдел.
    """
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
    """
    Смена пароля текущего пользователя.
    
    Требует ввода текущего пароля для подтверждения.
    После успешной смены отправляет email-уведомление.
    
    Raises:
        HTTPException 400: Неверный текущий пароль
    """
    # Проверяем текущий пароль
    if not verify_password(data.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Неверный текущий пароль")
    
    # Хешируем и сохраняем новый пароль
    current_user.password_hash = hash_password(data.new_password)
    await db.commit()
    
    # Отправляем email-уведомление о смене пароля
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
        # Не прерываем смену пароля при ошибке отправки email
        pass
    
    return {"message": "Password changed"}


@router.post("/forgot-password")
async def forgot_password(data: ForgotPassword, db: AsyncSession = Depends(get_db)):
    """
    Запрос сброса пароля — генерирует токен и отправляет email со ссылкой.
    
    Алгоритм:
    1. Находит пользователя по email
    2. Аннулирует старые неиспользованные токены
    3. Генерирует новый токен (срок жизни 1 час)
    4. Отправляет email со ссылкой на сброс
    
    Безопасность: всегда возвращает успех (защита от перебора email).
    """
    # Ищем пользователя по email
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()
    
    # Всегда возвращаем успех для защиты от enumeration
    if not user:
        return {"message": "Если email существует, письмо отправлено"}
    
    # Аннулируем старые токены
    old_tokens = await db.execute(
        select(PasswordResetToken).where(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used == False
        )
    )
    for token in old_tokens.scalars().all():
        token.used = True
    
    # Генерируем новый токен
    token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(hours=1)
    
    reset_token = PasswordResetToken(
        user_id=user.id,
        token=token,
        expires_at=expires_at
    )
    db.add(reset_token)
    await db.commit()
    
    # Формируем ссылку для сброса
    frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')
    reset_link = f"{frontend_url}/reset-password?token={token}"
    
    # Отправляем email
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
        # Логируем ошибку, но не показываем пользователю
        pass
    
    return {"message": "Если email существует, письмо отправлено"}


@router.post("/reset-password")
async def reset_password(data: ResetPassword, db: AsyncSession = Depends(get_db)):
    """
    Установка нового пароля по токену из письма.
    
    Проверяет:
    - Токен существует и не использован
    - Токен не истёк (1 час)
    - Пользователь существует
    
    Raises:
        HTTPException 400: Токен невалиден или истёк
    """
    # Ищем валидный токен
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
    
    # Получаем пользователя
    user_result = await db.execute(select(User).where(User.id == reset_token.user_id))
    user = user_result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=400, detail="Пользователь не найден")
    
    # Устанавливаем новый пароль
    user.password_hash = hash_password(data.new_password)
    reset_token.used = True
    await db.commit()
    
    return {"message": "Пароль успешно изменён"}