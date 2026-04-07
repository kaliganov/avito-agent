from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.db.models import Base


def _create_engine():
    url = settings.database_url
    kwargs: dict = {
        "echo": settings.app_env == "development",
        "pool_pre_ping": True,
    }
    if url.startswith("mysql"):
        kwargs["pool_recycle"] = 3600
        kwargs["connect_args"] = {"charset": "utf8mb4"}
    return create_async_engine(url, **kwargs)


engine = _create_engine()

async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with async_session_maker() as session:
        yield session
