"""
Comments and attachments routes
"""
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from pydantic import BaseModel

from shared import get_db, settings
from shared.models import Comment, Attachment

router = APIRouter()


class CommentCreate(BaseModel):
    content: str
    author_id: str = None  # Will be set from auth in future


def comment_to_dict(comment: Comment) -> dict:
    return {
        "id": str(comment.id),
        "incident_id": str(comment.incident_id),
        "author_id": str(comment.author_id),
        "author_name": comment.author.full_name if comment.author else None,
        "author_avatar": comment.author.avatar if comment.author else None,
        "content": comment.content,
        "created_at": comment.created_at.isoformat() if comment.created_at else None,
    }


@router.get("/incidents/{incident_id}/comments")
async def list_comments(incident_id: str, db: AsyncSession = Depends(get_db)):
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
    db: AsyncSession = Depends(get_db)
):
    author_id = data.author_id or "40000000-0000-0000-0000-000000000001"  # Default to admin
    
    comment = Comment(
        incident_id=uuid.UUID(incident_id),
        author_id=uuid.UUID(author_id),
        content=data.content
    )
    db.add(comment)
    await db.commit()
    await db.refresh(comment)
    
    # Reload with author
    result = await db.execute(
        select(Comment)
        .options(selectinload(Comment.author))
        .where(Comment.id == comment.id)
    )
    
    # Send notification about new comment
    from shared.tasks import notify_new_comment
    notify_new_comment.delay(incident_id, author_id, data.content)
    
    return comment_to_dict(result.scalar_one())


@router.delete("/comments/{comment_id}")
async def delete_comment(comment_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Comment).where(Comment.id == comment_id))
    comment = result.scalar_one_or_none()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    await db.delete(comment)
    await db.commit()
    return {"message": "Comment deleted"}


@router.get("/incidents/{incident_id}/attachments")
async def list_attachments(incident_id: str, db: AsyncSession = Depends(get_db)):
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
    uploader_id: str = "40000000-0000-0000-0000-000000000001",
    db: AsyncSession = Depends(get_db)
):
    import os
    import aiofiles
    
    # Create directory
    upload_dir = os.path.join("/app/uploads", incident_id)
    os.makedirs(upload_dir, exist_ok=True)
    
    # Save file
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    filename = f"{uuid.uuid4().hex}.{ext}"
    filepath = os.path.join(upload_dir, filename)
    
    contents = await file.read()
    async with aiofiles.open(filepath, "wb") as f:
        await f.write(contents)
    
    # Create record
    attachment = Attachment(
        incident_id=uuid.UUID(incident_id),
        uploader_id=uuid.UUID(uploader_id),
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
    """Delete an attachment. Only uploader or admin can delete."""
    import os
    
    result = await db.execute(select(Attachment).where(Attachment.id == attachment_id))
    attachment = result.scalar_one_or_none()
    
    if not attachment:
        raise HTTPException(status_code=404, detail="Файл не найден")
    
    # Delete file from disk
    if os.path.exists(attachment.filepath):
        os.remove(attachment.filepath)
    
    # Delete from database
    await db.delete(attachment)
    await db.commit()
    
    return {"message": "Файл удалён"}
