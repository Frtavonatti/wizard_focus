from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import get_current_user
from crud import stats as crud_stats
from database import get_db
from models.user import User
from schemas.user_stats import StatsRead

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/me", response_model=StatsRead)
async def get_my_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stats = await crud_stats.get_by_user(db, current_user.id)
    if stats is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Stats not found")
    return stats
