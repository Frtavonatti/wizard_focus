from fastapi import APIRouter, Depends, HTTPException, status
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from auth.hashing import hash_password, verify_password
from auth.jwt import create_access_token, create_refresh_token, decode_refresh_token
from crud import stats as crud_stats
from crud import users as crud_users
from database import get_db
from schemas.token import RefreshRequest, TokenResponse
from schemas.user import UserCreate, UserLogin

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(body: UserCreate, db: AsyncSession = Depends(get_db)):
    if await crud_users.get_by_email(db, body.email):
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Email already registered")
    if await crud_users.get_by_username(db, body.username):
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Username already taken")

    user = await crud_users.create(db, body.email, body.username, hash_password(body.password))
    await crud_stats.create_for_user(db, user.id)
    await db.commit()

    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/login", response_model=TokenResponse)
async def login(body: UserLogin, db: AsyncSession = Depends(get_db)):
    _invalid = HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    user = await crud_users.get_by_email(db, body.email)
    if user is None or user.hashed_password is None:
        raise _invalid
    if not verify_password(body.password, user.hashed_password):
        raise _invalid

    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    try:
        user_id = decode_refresh_token(body.refresh_token)
    except JWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")

    user = await crud_users.get_by_id(db, user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")

    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout():
    # Tokens are stateless JWTs — invalidation is client-side (discard tokens).
    # A server-side blocklist can be added in a future iteration if needed.
    return {"detail": "Logged out successfully"}

