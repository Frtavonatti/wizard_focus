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

_GITHUB_AUTH_URL = "https://github.com/login/oauth/authorize"
_GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
_GITHUB_USERINFO_URL = "https://api.github.com/user"
_GITHUB_EMAILS_URL = "https://api.github.com/user/emails"

_STATE_TYPE = "oauth_state"
_STATE_TTL_MINUTES = 10


def _build_state_token() -> tuple[str, str]:
    """Return (raw_state, signed_state_jwt)."""
    state = secrets.token_urlsafe(32)
    token = jwt.encode(
        {
            "state": state,
            "type": _STATE_TYPE,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=_STATE_TTL_MINUTES),
        },
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    return state, token


def build_google_auth_url(redirect_uri: str) -> tuple[str, str]:
    """
    Build the Google authorization URL and a signed state token.

    Returns (auth_url, state_token) where state_token is a short-lived signed
    JWT to be stored as an HttpOnly cookie and verified on callback.
    """
    state, state_token = _build_state_token()
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


def build_github_auth_url(redirect_uri: str) -> tuple[str, str]:
    """
    Build the GitHub authorization URL and a signed state token.

    Returns (auth_url, state_token).
    """
    state, state_token = _build_state_token()
    params = urlencode(
        {
            "client_id": settings.GITHUB_CLIENT_ID,
            "redirect_uri": redirect_uri,
            "scope": "read:user user:email",
            "state": state,
        }
    )
    return f"{_GITHUB_AUTH_URL}?{params}", state_token


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


async def exchange_google_code(code: str, redirect_uri: str) -> dict[str, Any]:
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


async def exchange_github_code(code: str, redirect_uri: str) -> dict[str, Any]:
    """Exchange an authorization code for a GitHub access token."""
    async with httpx.AsyncClient() as client:
        r = await client.post(
            _GITHUB_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.GITHUB_CLIENT_ID,
                "client_secret": settings.GITHUB_CLIENT_SECRET,
                "redirect_uri": redirect_uri,
            },
            headers={"Accept": "application/json"},
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


async def get_github_user_info(access_token: str) -> dict[str, Any]:
    """
    Fetch the authenticated user's profile from GitHub.

    If the user's email is private (null on /user), falls back to
    /user/emails to find the primary verified address.
    """
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/vnd.github+json",
    }
    async with httpx.AsyncClient() as client:
        r = await client.get(_GITHUB_USERINFO_URL, headers=headers)
        r.raise_for_status()
        user = r.json()

        if not user.get("email"):
            re = await client.get(_GITHUB_EMAILS_URL, headers=headers)
            re.raise_for_status()
            for entry in re.json():
                if entry.get("primary") and entry.get("verified"):
                    user["email"] = entry["email"]
                    break

    return user
