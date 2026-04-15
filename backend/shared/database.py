"""
Database connection for all microservices
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool

from shared.config import settings

# Use NullPool for Celery tasks to avoid connection issues
engine = create_async_engine(
    settings.DATABASE_URL, 
    echo=settings.DEBUG,
    poolclass=NullPool  # Disable connection pooling for async tasks
)

async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)


async def get_db():
    """Dependency for getting database session"""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
