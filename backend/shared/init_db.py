"""
Инициализация базы данных и создание начальных данных (seed data).

Запускается при первом запуске системы:
- Создаёт все таблицы по моделям
- Заполняет справочники: роли, статусы, приоритеты, отделы, категории
- Создаёт политику SLA для каждого приоритета
- Создаёт правила эскалации
- Создаёт пользователя admin@example.com / admin123
"""
import asyncio
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import async_session, engine
from shared.models import Base, User, Role, Department, Category, Priority, Status, SLAPolicy, EscalationRule, NotificationSettings


# === ПРЕДОПРЕДЕЛЁННЫЕ UUID ДЛЯ КОНСИСТЕНТНОСТИ ===
# Фиксированные ID позволяют перезапускать seed без дублирования
ROLE_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
ROLE_EXECUTOR_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")
ROLE_MANAGER_ID = uuid.UUID("00000000-0000-0000-0000-000000000003")
ROLE_ADMIN_ID = uuid.UUID("00000000-0000-0000-0000-000000000004")

STATUS_NEW_ID = uuid.UUID("10000000-0000-0000-0000-000000000001")
STATUS_ASSIGNED_ID = uuid.UUID("10000000-0000-0000-0000-000000000002")
STATUS_IN_PROGRESS_ID = uuid.UUID("10000000-0000-0000-0000-000000000003")
STATUS_RESOLVED_ID = uuid.UUID("10000000-0000-0000-0000-000000000004")
STATUS_CLOSED_ID = uuid.UUID("10000000-0000-0000-0000-000000000005")

PRIORITY_LOW_ID = uuid.UUID("20000000-0000-0000-0000-000000000001")
PRIORITY_MEDIUM_ID = uuid.UUID("20000000-0000-0000-0000-000000000002")
PRIORITY_HIGH_ID = uuid.UUID("20000000-0000-0000-0000-000000000003")
PRIORITY_CRITICAL_ID = uuid.UUID("20000000-0000-0000-0000-000000000004")

DEPT_IT_ID = uuid.UUID("30000000-0000-0000-0000-000000000001")
DEPT_HR_ID = uuid.UUID("30000000-0000-0000-0000-000000000002")
DEPT_SUPPORT_ID = uuid.UUID("30000000-0000-0000-0000-000000000003")

ADMIN_USER_ID = uuid.UUID("40000000-0000-0000-0000-000000000001")

# Хеш пароля "admin123" (bcrypt)
ADMIN_PASSWORD_HASH = "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.VTtYA/7.J6Ll8q"


async def init_db():
    """Создаёт все таблицы в БД на основе моделей."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def seed_data():
    """Заполняет БД начальными данными (только если БД пустая)."""
    async with async_session() as session:
        # Проверка: если уже есть данные, пропускаем
        result = await session.execute(select(Role))
        if result.scalar_one_or_none():
            print("Database already seeded, skipping...")
            return

        # === РОЛИ ===
        # 4 роли: User, Executor, Manager, Admin
        roles = [
            Role(id=ROLE_USER_ID, name="User", description="Обычный пользователь"),
            Role(id=ROLE_EXECUTOR_ID, name="Executor", description="Исполнитель инцидентов"),
            Role(id=ROLE_MANAGER_ID, name="Manager", description="Руководитель"),
            Role(id=ROLE_ADMIN_ID, name="Admin", description="Администратор системы"),
        ]
        session.add_all(roles)
        await session.flush()

        # === СТАТУСЫ ===
        # 5 статусов жизненного цикла инцидента
        statuses = [
            Status(id=STATUS_NEW_ID, name="Новый", color="#3B82F6"),
            Status(id=STATUS_ASSIGNED_ID, name="Назначен", color="#8B5CF6"),
            Status(id=STATUS_IN_PROGRESS_ID, name="В работе", color="#F59E0B"),
            Status(id=STATUS_RESOLVED_ID, name="Решён", color="#10B981"),
            Status(id=STATUS_CLOSED_ID, name="Закрыт", color="#059669"),
        ]
        session.add_all(statuses)
        await session.flush()

        # === ПРИОРИТЕТЫ ===
        # 4 уровня приоритета с цветовой индикацией
        priorities = [
            Priority(id=PRIORITY_LOW_ID, name="Низкий", level=1, color="#6B7280"),
            Priority(id=PRIORITY_MEDIUM_ID, name="Средний", level=2, color="#3B82F6"),
            Priority(id=PRIORITY_HIGH_ID, name="Высокий", level=3, color="#F59E0B"),
            Priority(id=PRIORITY_CRITICAL_ID, name="Критический", level=4, color="#EF4444"),
        ]
        session.add_all(priorities)
        await session.flush()

        # === ОТДЕЛЫ ===
        # 3 отдела по умолчанию
        departments = [
            Department(id=DEPT_IT_ID, name="IT отдел", description="Техническая поддержка"),
            Department(id=DEPT_HR_ID, name="HR отдел", description="Управление персоналом"),
            Department(id=DEPT_SUPPORT_ID, name="Служба поддержки", description="Первая линия поддержки"),
        ]
        session.add_all(departments)
        await session.flush()

        # === КАТЕГОРИИ ИНЦИДЕНТОВ ===
        # 5 категорий для классификации инцидентов
        categories = [
            Category(id=uuid.uuid4(), name="Техническая проблема", description="Проблемы с оборудованием или ПО", is_active=True),
            Category(id=uuid.uuid4(), name="Доступ и учётные записи", description="Проблемы с доступом, паролями", is_active=True),
            Category(id=uuid.uuid4(), name="Сеть и связь", description="Проблемы с сетью, интернетом, телефонией", is_active=True),
            Category(id=uuid.uuid4(), name="Запрос на обслуживание", description="Заявки на установку, настройку", is_active=True),
            Category(id=uuid.uuid4(), name="Другое", description="Прочие запросы", is_active=True),
        ]
        session.add_all(categories)
        await session.flush()

        # === SLA-ПОЛИТИКИ ===
        # Время решения для каждого приоритета (в часах)
        sla_policies = [
            SLAPolicy(id=uuid.uuid4(), priority_id=PRIORITY_LOW_ID, resolution_hours=72, description="Низкий приоритет - 72 часа"),
            SLAPolicy(id=uuid.uuid4(), priority_id=PRIORITY_MEDIUM_ID, resolution_hours=24, description="Средний приоритет - 24 часа"),
            SLAPolicy(id=uuid.uuid4(), priority_id=PRIORITY_HIGH_ID, resolution_hours=8, description="Высокий приоритет - 8 часов"),
            SLAPolicy(id=uuid.uuid4(), priority_id=PRIORITY_CRITICAL_ID, resolution_hours=4, description="Критический приоритет - 4 часа"),
        ]
        session.add_all(sla_policies)
        await session.flush()

        # === ПРАВИЛА ЭСКАЛАЦИИ ===
        # L1: 80% SLA → уведомление Manager'а
        # L2: просрочка → уведомление Admin'а
        escalation_rules = [
            EscalationRule(id=uuid.uuid4(), level=1, notify_role_id=ROLE_MANAGER_ID, condition_type="percent_80", is_active=True),
            EscalationRule(id=uuid.uuid4(), level=2, notify_role_id=ROLE_ADMIN_ID, condition_type="overdue", is_active=True),
        ]
        session.add_all(escalation_rules)
        await session.flush()

        # === АДМИНИСТРАТОР ===
        # Учётная запись по умолчанию: admin@example.com / admin123
        admin_user = User(
            id=ADMIN_USER_ID,
            email="admin@example.com",
            password_hash=ADMIN_PASSWORD_HASH,
            full_name="Администратор",
            role_id=ROLE_ADMIN_ID,
            department_id=DEPT_IT_ID,
            is_active=True
        )
        session.add(admin_user)
        await session.flush()

        # === НАСТРОЙКИ УВЕДОМЛЕНИЙ ДЛЯ АДМИНА ===
        # Все уведомления включены по умолчанию
        all_enabled = {"internal": True, "email": True}
        notif_settings = NotificationSettings(
            id=uuid.uuid4(),
            user_id=ADMIN_USER_ID,
            incident_created=all_enabled,
            assigned_executor=all_enabled,
            new_comment=all_enabled,
            status_changed=all_enabled,
            incident_resolved=all_enabled,
            overdue=all_enabled,
            escalation=all_enabled,
            priority_changed=all_enabled
        )
        session.add(notif_settings)

        await session.commit()
        print("Database seeded successfully!")
        print("Admin credentials: admin@example.com / admin123")


async def main():
    """Точка входа для инициализации БД."""
    print("Initializing database...")
    await init_db()
    print("Seeding data...")
    await seed_data()
    print("Done!")


if __name__ == "__main__":
    asyncio.run(main())