"""
Скрипт сброса пароля администратора.

Используется при потере пароля от учётной записи admin@example.com.
Устанавливает пароль "admin123" (можно изменить в коде).

Запуск:
    docker-compose exec user-service python -m shared.reset_admin
    # или локально: python -m shared.reset_admin
"""
import asyncio
from sqlalchemy import text
from shared.database import async_session
from shared.utils import hash_password

async def main():
    """Сбрасывает пароль администратора на "admin123"."""
    # Генерируем новый хеш пароля
    new_hash = hash_password("admin123")
    print(f"New hash: {new_hash}")
    
    # Обновляем пароль в БД
    async with async_session() as db:
        result = await db.execute(
            text("UPDATE users SET password_hash = :hash WHERE email = 'admin@example.com'"),
            {"hash": new_hash}
        )
        await db.commit()
        print(f"Updated {result.rowcount} rows")

asyncio.run(main())
