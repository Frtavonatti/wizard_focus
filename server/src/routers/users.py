from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import get_current_user
from auth.hashing import hash_password
from crud import users as crud_users
from database import get_db
from models.user import User
from schemas.user import UserRead, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserRead)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.patch("/me", response_model=UserRead)
async def update_me(
    body: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    changes = body.model_dump(exclude_unset=True, exclude_none=True)
    if not changes:
        return current_user

    if "email" in changes and changes["email"] != current_user.email:
        if await crud_users.get_by_email(db, changes["email"]):
            raise HTTPException(status.HTTP_409_CONFLICT, detail="Email already taken")

    if "username" in changes and changes["username"] != current_user.username:
        if await crud_users.get_by_username(db, changes["username"]):
            raise HTTPException(status.HTTP_409_CONFLICT, detail="Username already taken")

    if "password" in changes:
        changes["hashed_password"] = hash_password(changes.pop("password"))

    user = await crud_users.update(db, current_user, changes)
    await db.commit()
    return user


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await crud_users.delete(db, current_user)
    await db.commit()
