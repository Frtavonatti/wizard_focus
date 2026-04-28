import re
import secrets

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from auth.jwt import create_access_token, create_refresh_token
from auth.oauth import build_google_auth_url, exchange_code, get_google_user_info, verify_state
from config import settings
from crud import oauth_accounts as crud_oauth
from crud import stats as crud_stats
from crud import users as crud_users
from database import get_db

router = APIRouter(prefix="/auth", tags=["oauth"])

_OAUTH_STATE_COOKIE = "oauth_state"


@router.get("/google")
async def google_login(request: Request) -> RedirectResponse:
    redirect_uri = str(request.url_for("google_callback"))
    auth_url, state_token = build_google_auth_url(redirect_uri)
    response = RedirectResponse(auth_url)
    response.set_cookie(
        _OAUTH_STATE_COOKIE,
        state_token,
        max_age=600,
        httponly=True,
        samesite="lax",
        secure=not settings.DEBUG,
    )
    return response


@router.get("/google/callback", name="google_callback")
async def google_callback(
    request: Request,
    db: AsyncSession = Depends(get_db),
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    if error or not code or not state:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="OAuth error or missing parameters")

    state_cookie = request.cookies.get(_OAUTH_STATE_COOKIE)
    if not state_cookie:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Missing state cookie")

    try:
        verify_state(state, state_cookie)
    except ValueError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Invalid OAuth state")

    redirect_uri = str(request.url_for("google_callback"))

    try:
        token_data = await exchange_code(code, redirect_uri)
    except httpx.HTTPStatusError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Failed to exchange code with Google")

    try:
        user_info = await get_google_user_info(token_data["access_token"])
    except httpx.HTTPStatusError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Failed to fetch user info from Google")

    provider_user_id: str = user_info.get("sub", "")
    email: str | None = user_info.get("email")

    if not provider_user_id or not email:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Incomplete profile from Google")

    # Find or create user + link OAuth account
    oauth_account = await crud_oauth.get_by_provider(db, "google", provider_user_id)
    if oauth_account:
        user = await crud_users.get_by_id(db, oauth_account.user_id)
    else:
        # Link to an existing password-based account with the same email, or create new
        user = await crud_users.get_by_email(db, email)
        if not user:
            username = await _unique_username(db, user_info)
            user = await crud_users.create(db, email, username)
            await crud_stats.create_for_user(db, user.id)
        await crud_oauth.create(db, user.id, "google", provider_user_id)

    await db.commit()

    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)

    frontend_redirect = (
        f"{settings.FRONTEND_URL}/auth/callback"
        f"?access_token={access_token}&refresh_token={refresh_token}"
    )
    response = RedirectResponse(frontend_redirect)
    response.delete_cookie(_OAUTH_STATE_COOKIE)
    return response


async def _unique_username(db: AsyncSession, user_info: dict) -> str:
    """Derive a unique username from a Google profile."""
    base = re.sub(r"[^a-z0-9]", "", user_info.get("name", "").lower())
    if not base:
        base = user_info.get("email", "user").split("@")[0]
    base = base[:28]
    if not await crud_users.get_by_username(db, base):
        return base
    for i in range(1, 100):
        candidate = f"{base[:25]}{i}"
        if not await crud_users.get_by_username(db, candidate):
            return candidate
    return f"{base[:20]}{secrets.token_urlsafe(4)}"
