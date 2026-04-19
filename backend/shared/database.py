"""
Настройка подключения к базе данных для всех микросервисов.

Используется:
- SQLAlchemy 2.0 (async)
- asyncpg — асинхронный драйвер PostgreSQL
- NullPool — отключение пула соединений для стабильности в Celery
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool

from shared.config import settings

# Асинхронный engine для подключения к БД
# echo=settings.DEBUG — логировать SQL-запросы в режиме отладки
# NullPool — отключаем пул соединений для избежания проблем в Celery-задачах
engine = create_async_engine(
    settings.DATABASE_URL, 
    echo=settings.DEBUG,
    poolclass=NullPool
)

# Factory для создания сессий БД
# autoflush=False — не делать автоматический flush перед запросами
async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)


async def get_db():
    """
    Dependency для получения сессии БД в endpoint'ах.
    
    Используется в FastAPI как Depends(get_db).
    Автоматически делает commit при успехе или rollback при ошибке.
    """
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
