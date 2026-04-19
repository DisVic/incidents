"""
Инициализация настроек уведомлений для всех пользователей.

Скрипт создаёт или обновляет настройки уведомлений:
- Admin/Manager: все уведомления включены (internal + email)
- Executor/User: email-уведомления только для важных событий

Запуск:
    python -m shared.init_notification_settings
"""
import asyncio
from sqlalchemy import select
from shared.database import async_session
from shared.models import User, Role, NotificationSettings


async def init_notification_settings():
    """Создаёт настройки уведомлений для всех пользователей с роль-зависимыми дефолтами."""
    async with async_session() as db:
        # Получаем всех пользователей
        result = await db.execute(select(User))
        users = result.scalars().all()
        
        created_count = 0
        updated_count = 0
        
        for user in users:
            # Проверяем, есть ли уже настройки
            existing = await db.execute(
                select(NotificationSettings).where(NotificationSettings.user_id == user.id)
            )
            ns = existing.scalar_one_or_none()
            
            # Получаем роль пользователя
            role_result = await db.execute(
                select(Role).where(Role.id == user.role_id)
            )
            role = role_result.scalar_one_or_none()
            role_name = role.name if role else "Executor"
            
            # Настройки по умолчанию в зависимости от роли
            all_enabled = {"internal": True, "email": True}
            
            if role_name == "Admin":
                # Admin получает все уведомления
                settings = {
                    "incident_created": all_enabled,
                    "assigned_executor": all_enabled,
                    "new_comment": all_enabled,
                    "status_changed": all_enabled,
                    "incident_resolved": all_enabled,
                    "overdue": all_enabled,
                    "escalation": all_enabled
                }
            elif role_name == "Manager":
                # Manager получает все уведомления
                settings = {
                    "incident_created": all_enabled,
                    "assigned_executor": all_enabled,
                    "new_comment": all_enabled,
                    "status_changed": all_enabled,
                    "incident_resolved": all_enabled,
                    "overdue": all_enabled,
                    "escalation": all_enabled
                }
            else:
                # Executor получает только важные email-уведомления
                settings = {
                    "incident_created": {"internal": True, "email": False},
                    "assigned_executor": all_enabled,
                    "new_comment": all_enabled,
                    "status_changed": all_enabled,
                    "incident_resolved": all_enabled,
                    "overdue": {"internal": True, "email": False},
                    "escalation": {"internal": True, "email": False}
                }
            
            if ns:
                # Обновляем существующие настройки
                for key, value in settings.items():
                    setattr(ns, key, value)
                updated_count += 1
            else:
                # Создаём новые настройки
                ns = NotificationSettings(
                    user_id=user.id,
                    **settings
                )
                db.add(ns)
                created_count += 1
        
        await db.commit()
        print(f"Created {created_count} new settings, updated {updated_count} existing settings")
        return {"created": created_count, "updated": updated_count}


if __name__ == "__main__":
    asyncio.run(init_notification_settings())
