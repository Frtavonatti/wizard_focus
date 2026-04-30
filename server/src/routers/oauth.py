import re
import secrets
from enum import Enum

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from auth.jwt import (
    create_access_token,
    create_exchange_code,
    create_refresh_token,
    decode_exchange_code,
)
from jose import JWTError
from auth.oauth import (
    build_github_auth_url,
    build_google_auth_url,
    exchange_google_code,
    exchange_github_code,
    get_github_user_info,
    get_google_user_info,
    verify_state,
)
from config import settings
from crud import oauth_accounts as crud_oauth
from crud import stats as crud_stats
from crud import users as crud_users
from database import get_db
from schemas.token import ExchangeCodeRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["oauth"])

_OAUTH_STATE_COOKIE = "oauth_state"


class OAuthProvider(str, Enum):
    google = "google"
    github = "github"


@router.get("/{provider}")
async def oauth_login(provider: OAuthProvider, request: Request) -> RedirectResponse:
    if provider == OAuthProvider.google:
        if not settings.GOOGLE_CLIENT_ID:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail="Google OAuth is not configured")
        redirect_uri = str(request.url_for("oauth_callback", provider=provider.value))
        auth_url, state_token = build_google_auth_url(redirect_uri)
    else:
        if not settings.GITHUB_CLIENT_ID:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail="GitHub OAuth is not configured")
        redirect_uri = str(request.url_for("oauth_callback", provider=provider.value))
        auth_url, state_token = build_github_auth_url(redirect_uri)
    response = RedirectResponse(auth_url)
    response.set_cookie(
        _OAUTH_STATE_COOKIE,
        state_token,
        max_age=600,
        httponly=True,
        samesite="lax",
        secure=request.url.scheme == "https",
    )
    return response


async def _fetch_provider_data(
    provider: OAuthProvider, code: str, redirect_uri: str
) -> tuple[str, dict]:
    """Exchange auth code for user info. Returns (provider_user_id, user_info).
    Raises HTTPException 400 on any provider-side failure.
    """
    try:
        if provider == OAuthProvider.google:
            token_data = await exchange_google_code(code, redirect_uri)
            user_info = await get_google_user_info(token_data["access_token"])
            return user_info.get("sub", ""), user_info
        else:
            token_data = await exchange_github_code(code, redirect_uri)
            user_info = await get_github_user_info(token_data["access_token"])
            return str(user_info.get("id", "")), user_info
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to authenticate with {provider.value.title()}: {exc.response.status_code}",
        )


@router.get("/{provider}/callback", name="oauth_callback")
async def oauth_callback(
    provider: OAuthProvider,
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

    redirect_uri = str(request.url_for("oauth_callback", provider=provider.value))
    provider_user_id, user_info = await _fetch_provider_data(provider, code, redirect_uri)

    email: str | None = user_info.get("email")
    if not provider_user_id or not email:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=f"Incomplete profile from {provider.value.title()}",
        )

    user = await _find_or_create_user(db, provider.value, provider_user_id, email, user_info)
    await db.commit()

    exchange_code = create_exchange_code(user.id)
    frontend_redirect = f"{settings.FRONTEND_URL}/auth/callback?code={exchange_code}"
    response = RedirectResponse(frontend_redirect)
    response.delete_cookie(_OAUTH_STATE_COOKIE)
    return response


@router.post("/token/exchange", response_model=TokenResponse)
async def exchange_token(body: ExchangeCodeRequest) -> TokenResponse:
    """Exchange a short-lived OAuth exchange code for access + refresh tokens."""
    try:
        user_id = decode_exchange_code(body.code)
    except JWTError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Invalid or expired exchange code")
    return TokenResponse(
        access_token=create_access_token(user_id),
        refresh_token=create_refresh_token(user_id),
    )


async def _unique_username(db: AsyncSession, user_info: dict) -> str:
    base = re.sub(r"[^a-z0-9]", "", user_info.get("name", "").lower())
    if not base:
        base = user_info.get("login", user_info.get("email", "user").split("@")[0])
        base = re.sub(r"[^a-z0-9]", "", base.lower())
    base = base[:28] or "user"
    if not await crud_users.get_by_username(db, base):
        return base
    for i in range(1, 100):
        candidate = f"{base[:25]}{i}"
        if not await crud_users.get_by_username(db, candidate):
            return candidate
    return f"{base[:20]}{secrets.token_hex(4)}"


async def _find_or_create_user(db: AsyncSession, provider: str, provider_user_id: str, email: str, user_info: dict):
    oauth_account = await crud_oauth.get_by_provider(db, provider, provider_user_id)
    if oauth_account:
        return await crud_users.get_by_id(db, oauth_account.user_id)

    user = await crud_users.get_by_email(db, email)
    if not user:
        username = await _unique_username(db, user_info)
        user = await crud_users.create(db, email, username)
        await crud_stats.create_for_user(db, user.id)
    await crud_oauth.create(db, user.id, provider, provider_user_id)
    return user
