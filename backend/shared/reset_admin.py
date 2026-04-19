"""
Сброс пароля администратора
Используется для восстановления доступа к системе
"""
import asyncio
from sqlalchemy import select
from shared.database import async_session_maker
from shared.models import User, Role
from shared.utils import hash_password


async def reset_admin_password(new_password: str = "admin123"):
    """Сброс пароля админа на указанный"""
    async with async_session_maker() as session:
        # Находим роль Admin
        result = await session.execute(select(Role).where(Role.name == "Admin"))
        admin_role = result.scalar_one_or_none()
        
        if not admin_role:
            print("Роль Admin не найдена")
            return
        
        # Находим первого пользователя с ролью Admin
        result = await session.execute(
            select(User).where(User.role_id == admin_role.id)
        )
        admin_user = result.scalar_one_or_none()
        
        if not admin_user:
            print("Пользователь Admin не найден")
            return
        
        # Обновляем пароль
        admin_user.password_hash = hash_password(new_password)
        await session.commit()
        
        print(f"Пароль администратора {admin_user.email} изменён на: {new_password}")


if __name__ == "__main__":
    asyncio.run(reset_admin_password())
