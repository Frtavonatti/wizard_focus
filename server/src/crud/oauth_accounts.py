from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.oauth_account import OAuthAccount


async def get_by_provider(
    db: AsyncSession, provider: str, provider_user_id: str
) -> OAuthAccount | None:
    result = await db.execute(
        select(OAuthAccount).where(
            OAuthAccount.provider == provider,
            OAuthAccount.provider_user_id == provider_user_id,
        )
    )
    return result.scalar_one_or_none()


async def create(
    db: AsyncSession, user_id: UUID, provider: str, provider_user_id: str
) -> OAuthAccount:
    account = OAuthAccount(
        user_id=user_id, provider=provider, provider_user_id=provider_user_id
    )
    db.add(account)
    await db.flush()
    await db.refresh(account)
    return account
