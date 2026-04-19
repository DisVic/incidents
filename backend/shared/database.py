"""Подключение к базе данных для всех микросервисов"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool

from shared.config import settings


# Движок для асинхронного подключения к PostgreSQL
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,  # Логирование SQL-запросов в режиме отладки
    poolclass=NullPool  # Без пула соединений (для serverless/Celery)
)


# Фабрика сессий для работы с БД
async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Не очищать объекты после коммита
    autoflush=False  # Отключить авто-flush перед запросами
)


async def get_db():
    """Зависимость FastAPI для получения сессии БД"""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
