"""
API комментариев и вложений к инцидентам.

Endpoint'ы:
- GET /incidents/{id}/comments — список комментариев
- POST /incidents/{id}/comments — добавить комментарий
- DELETE /comments/{id} — удалить комментарий
- GET /incidents/{id}/attachments — список вложений
- POST /incidents/{id}/attachments — загрузить файл
- GET /attachments/{id}/download — скачать файл
- DELETE /attachments/{id} — удалить файл
"""
import uuid
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Body, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from pydantic import BaseModel

from shared import get_db, settings
from shared.models import Comment, Attachment, User

router = APIRouter()


class CommentCreate(BaseModel):
    """Данные для создания комментария."""
    content: str


class CommentUpdate(BaseModel):
    """Данные для обновления комментария."""
    content: str


def comment_to_dict(comment: Comment) -> dict:
    """Конвертация ORM-объекта комментария в словарь."""
    return {
        "id": str(comment.id),
        "incident_id": str(comment.incident_id),
        "author_id": str(comment.author_id),
        "author_name": comment.author.full_name if comment.author else None,
        "author_avatar": comment.author.avatar if comment.author else None,
        "content": comment.content,
        "created_at": comment.created_at.isoformat() if comment.created_at else None,
    }


async def get_current_user_id_optional(request: Request) -> Optional[str]:
    """
    Извлекает user_id из JWT токена в заголовке Authorization.
    
    Возвращает None если токен отсутствует или невалиден (не выбрасывает ошибку).
    """
    auth_header = request.headers.get("Authorization")
    
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    
    token = auth_header.split(" ")[1]
    from shared import decode_token
    
    try:
        payload = decode_token(token, settings.SECRET_KEY)
        # JWT токен использует 'sub' для user_id, а не 'user_id'
        if payload and "sub" in payload:
            return payload["sub"]
    except Exception:
        pass
    
    return None

    token = auth_header.split(" ")[1]
    from shared import decode_token

    try:
        payload = decode_token(token, settings.SECRET_KEY)
        print(f"[DEBUG] Decoded payload: {payload}")
        if payload and "user_id" in payload:
            print(f"[DEBUG] Extracted user_id: {payload['user_id']}")
            return payload["user_id"]
        # JWT токен использует 'sub' для user_id, а не 'user_id'
        if payload and "sub" in payload:
            user_id = payload["sub"]
            print(f"[DEBUG] Extracted user_id from 'sub': {user_id}")
            return user_id
    except Exception as e:
        print(f"[DEBUG] Error decoding token: {e}")
        pass
    
    return None


async def get_current_user_id(request: Request) -> str:
    """
    Извлекает user_id из JWT токена в заголовке Authorization.
    Требует валидную аутентификацию.
    """
    user_id = await get_current_user_id_optional(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Требуется аутентификация")
    return user_id


@router.get("/incidents/{incident_id}/comments")
async def list_comments(incident_id: str, db: AsyncSession = Depends(get_db)):
    """Список комментариев инцидента (от старых к новым)."""
    result = await db.execute(
        select(Comment)
        .options(selectinload(Comment.author))
        .where(Comment.incident_id == incident_id)
        .order_by(Comment.created_at.asc())
    )
    comments = result.scalars().all()
    return [comment_to_dict(c) for c in comments]


@router.post("/incidents/{incident_id}/comments")
async def create_comment(
    incident_id: str,
    data: CommentCreate,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Добавить комментарий к инциденту.
    
    Автор берётся из JWT токена (текущий пользователь).
    Если токен не валиден - используется Admin по умолчанию.
    Отправляет уведомление всем участникам инцидента.
    """
    # Получаем user_id из JWT токена (опционально)
    user_id = await get_current_user_id_optional(request)
    
    # Если токен не валиден, используем Admin по умолчанию
    if not user_id:
        user_id = "40000000-0000-0000-0000-000000000001"  # admin
    
    # Проверяем, что пользователь существует
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        # Если пользователь не найден, используем admin
        user_id = "40000000-0000-0000-0000-000000000001"
        result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
        user = result.scalar_one_or_none()
    
    comment = Comment(
        incident_id=uuid.UUID(incident_id),
        author_id=uuid.UUID(user_id),
        content=data.content
    )
    db.add(comment)
    await db.commit()
    await db.refresh(comment)
    
    # Перезагружаем с данными автора
    result = await db.execute(
        select(Comment)
        .options(selectinload(Comment.author))
        .where(Comment.id == comment.id)
    )

    # Отправляем уведомление
    from shared.tasks import notify_new_comment
    notify_new_comment.delay(incident_id, user_id, data.content)
    
    return comment_to_dict(result.scalar_one())


@router.delete("/comments/{comment_id}")
async def delete_comment(
    comment_id: str, 
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Удаление комментария.
    
    Может удалить:
    - Создатель комментария
    - Администратор
    """
    # Получаем user_id из JWT токена
    user_id = await get_current_user_id_optional(request)
    
    if not user_id:
        raise HTTPException(status_code=401, detail="Требуется аутентификация")
    
    # Ищем комментарий
    result = await db.execute(
        select(Comment)
        .where(Comment.id == uuid.UUID(comment_id))
    )
    comment = result.scalar_one_or_none()
    
    if not comment:
        raise HTTPException(status_code=404, detail="Комментарий не найден")
    
    # Проверяем права
    is_creator = str(comment.author_id) == user_id
    
    # Проверяем, админ ли пользователь
    is_admin = False
    user_result = await db.execute(
        select(User)
        .options(selectinload(User.role))
        .where(User.id == uuid.UUID(user_id))
    )
    current_user = user_result.scalar_one_or_none()
    if current_user and current_user.role:
        is_admin = current_user.role.name == "Admin"
    
    if not is_creator and not is_admin:
        raise HTTPException(status_code=403, detail="Нет прав на удаление этого комментария")
    
    await db.delete(comment)
    await db.commit()
    return {"message": "Комментарий удалён"}
    

@router.put("/comments/{comment_id}")
async def update_comment(
    comment_id: str,
    data: CommentUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Обновление комментария.
    
    Может редактировать только создатель комментария.
    """
    # Получаем user_id из JWT токена
    user_id = await get_current_user_id_optional(request)
    
    if not user_id:
        raise HTTPException(status_code=401, detail="Требуется аутентификация")
    
    # Ищем комментарий
    result = await db.execute(
        select(Comment)
        .options(selectinload(Comment.author))
        .where(Comment.id == uuid.UUID(comment_id))
    )
    comment = result.scalar_one_or_none()
    
    if not comment:
        raise HTTPException(status_code=404, detail="Комментарий не найден")
    
    # Проверяем права - только создатель
    if str(comment.author_id) != user_id:
        raise HTTPException(status_code=403, detail="Нет прав на редактирование этого комментария")
    
    # Обновляем контент
    comment.content = data.content
    await db.commit()
    await db.refresh(comment)
    
    return comment_to_dict(comment)
    

@router.get("/incidents/{incident_id}/attachments")
async def list_attachments(incident_id: str, db: AsyncSession = Depends(get_db)):
    """Список вложений инцидента (новые первые)."""
    result = await db.execute(
        select(Attachment)
        .where(Attachment.incident_id == incident_id)
        .order_by(Attachment.created_at.desc())
    )
    attachments = result.scalars().all()
    return [
        {
            "id": str(a.id),
            "incident_id": str(a.incident_id),
            "uploader_id": str(a.uploader_id),
            "filename": a.filename,
            "filesize": a.filesize,
            "mime_type": a.mime_type,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in attachments
    ]


@router.post("/incidents/{incident_id}/attachments")
async def upload_attachment(
    incident_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    request: Request = Request
):
    """
    Загрузка файла к инциденту.
    
    Файлы сохраняются в /app/uploads/{incident_id}/
    uploader_id берётся из JWT токена. Если токен не валиден - используется Admin.
    """
    import os
    import aiofiles
    
    # Получаем user_id из JWT токена (опционально)
    user_id = await get_current_user_id_optional(request)
    
    # Если токен не валиден, используем Admin по умолчанию
    if not user_id:
        user_id = "40000000-0000-0000-0000-000000000001"  # admin
    
    # Создаём директорию
    upload_dir = os.path.join("/app/uploads", incident_id)
    os.makedirs(upload_dir, exist_ok=True)
    
    # Сохраняем файл
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    filename = f"{uuid.uuid4().hex}.{ext}"
    filepath = os.path.join(upload_dir, filename)
    
    contents = await file.read()
    async with aiofiles.open(filepath, "wb") as f:
        await f.write(contents)
    
    # Создаём запись в БД
    attachment = Attachment(
        incident_id=uuid.UUID(incident_id),
        uploader_id=uuid.UUID(user_id),
        filename=file.filename,
        filepath=filepath,
        filesize=len(contents),
        mime_type=file.content_type
    )
    db.add(attachment)
    await db.commit()
    await db.refresh(attachment)
    
    return {
        "id": str(attachment.id),
        "incident_id": str(attachment.incident_id),
        "uploader_id": str(attachment.uploader_id),
        "filename": attachment.filename,
        "filesize": attachment.filesize,
        "mime_type": attachment.mime_type,
        "created_at": attachment.created_at.isoformat() if attachment.created_at else None,
    }


@router.get("/attachments/{attachment_id}/download")
async def download_attachment(attachment_id: str, db: AsyncSession = Depends(get_db)):
    """Скачивание файла по ID."""
    from fastapi.responses import FileResponse
    
    result = await db.execute(select(Attachment).where(Attachment.id == attachment_id))
    attachment = result.scalar_one_or_none()
    
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")
    
    import os
    if not os.path.exists(attachment.filepath):
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        path=attachment.filepath,
        filename=attachment.filename,
        media_type=attachment.mime_type
    )


@router.delete("/attachments/{attachment_id}")
async def delete_attachment(
    attachment_id: str, 
    user_id: str = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Удаление файла.
    
    Может удалить только загрузивший пользователь или администратор.
    """
    import os
    
    result = await db.execute(select(Attachment).where(Attachment.id == attachment_id))
    attachment = result.scalar_one_or_none()
    
    if not attachment:
        raise HTTPException(status_code=404, detail="Файл не найден")
    
    # Удаляем файл с диска
    if os.path.exists(attachment.filepath):
        os.remove(attachment.filepath)
    
    # Удаляем из БД
    await db.delete(attachment)
    await db.commit()
    
    return {"message": "Файл удалён"}
