import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

import httpx
from jose import JWTError, jwt

from config import settings

_GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

_STATE_TYPE = "oauth_state"
_STATE_TTL_MINUTES = 10


def build_google_auth_url(redirect_uri: str) -> tuple[str, str]:
    """
    Build the Google authorization URL and a signed state token.

    Returns (auth_url, state_token) where state_token is a short-lived signed
    JWT to be stored as an HttpOnly cookie and verified on callback.
    """
    state = secrets.token_urlsafe(32)
    state_token = jwt.encode(
        {
            "state": state,
            "type": _STATE_TYPE,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=_STATE_TTL_MINUTES),
        },
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    params = urlencode(
        {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "access_type": "online",
        }
    )
    return f"{_GOOGLE_AUTH_URL}?{params}", state_token


def verify_state(state_from_query: str, state_token_from_cookie: str) -> None:
    """
    Validate the OAuth state parameter against the signed cookie.
    Raises ValueError on any mismatch — caller should map this to 400.
    """
    try:
        payload = jwt.decode(
            state_token_from_cookie,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except JWTError as exc:
        raise ValueError("Invalid state token") from exc
    if payload.get("type") != _STATE_TYPE:
        raise ValueError("Invalid state token type")
    if payload.get("state") != state_from_query:
        raise ValueError("State mismatch — possible CSRF")


async def exchange_code(code: str, redirect_uri: str) -> dict[str, Any]:
    """Exchange an authorization code for Google tokens."""
    async with httpx.AsyncClient() as client:
        r = await client.post(
            _GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        r.raise_for_status()
        return r.json()


async def get_google_user_info(access_token: str) -> dict[str, Any]:
    """Fetch the authenticated user's profile from Google."""
    async with httpx.AsyncClient() as client:
        r = await client.get(
            _GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        r.raise_for_status()
        return r.json()
