"""
Инициализация настроек уведомлений для всех пользователей
Запускается при старте системы для создания default-настроек
"""
import asyncio
from sqlalchemy import select
from shared.database import async_session_maker
from shared.models import NotificationSettings, User


async def init_all():
    """Создание настроек уведомлений для пользователей без них"""
    async with async_session_maker() as session:
        # Получаем всех пользователей
        result = await session.execute(select(User))
        users = result.scalars().all()
        
        created_count = 0
        for user in users:
            # Проверяем наличие настроек
            existing = await session.execute(
                select(NotificationSettings).where(NotificationSettings.user_id == user.id)
            )
            if not existing.scalar_one_or_none():
                # Создаём настройки со всеми включенными уведомлениями
                all_enabled = {"internal": True, "email": True}
                settings = NotificationSettings(
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
                session.add(settings)
                created_count += 1
        
        if created_count > 0:
            await session.commit()
            print(f"Создано настроек уведомлений: {created_count}")
        else:
            print("Все пользователи имеют настройки уведомлений")


if __name__ == "__main__":
    asyncio.run(init_all())
