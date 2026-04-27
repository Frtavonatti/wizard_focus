from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.user_stats import Stats


async def get_by_user(db: AsyncSession, user_id: UUID) -> Stats | None:
    result = await db.execute(select(Stats).where(Stats.user_id == user_id))
    return result.scalar_one_or_none()


async def create_for_user(db: AsyncSession, user_id: UUID) -> Stats:
    stats = Stats(user_id=user_id)
    db.add(stats)
    await db.flush()
    await db.refresh(stats)
    return stats
