from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from config import get_settings


class Base(DeclarativeBase):
    pass


@lru_cache
def _get_engine():
    s = get_settings()
    return create_async_engine(s.DATABASE_URL, echo=s.DEBUG)


@lru_cache
def _get_session_maker() -> async_sessionmaker:
    return async_sessionmaker(
        bind=_get_engine(),
        class_=AsyncSession,
        expire_on_commit=False,
    )


def AsyncSessionLocal() -> AsyncSession:
    """Return a new AsyncSession (backward-compatible callable used by the health check)."""
    return _get_session_maker()()


async def get_db():
    async with _get_session_maker()() as session:
        yield session
