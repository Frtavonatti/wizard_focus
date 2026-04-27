from datetime import datetime, timedelta, timezone
from uuid import UUID

from jose import JWTError, jwt

from config import settings

_ACCESS = "access"
_REFRESH = "refresh"


def _make_token(subject: UUID, token_type: str, expires_delta: timedelta) -> str:
    expire = datetime.now(timezone.utc) + expires_delta
    payload = {"sub": str(subject), "type": token_type, "exp": expire}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_access_token(user_id: UUID) -> str:
    return _make_token(
        user_id,
        _ACCESS,
        timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def create_refresh_token(user_id: UUID) -> str:
    return _make_token(
        user_id,
        _REFRESH,
        timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )


def decode_access_token(token: str) -> UUID:
    """Decode and validate an access token. Raises JWTError on any failure."""
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    if payload.get("type") != _ACCESS:
        raise JWTError("Invalid token type")
    return UUID(payload["sub"])


def decode_refresh_token(token: str) -> UUID:
    """Decode and validate a refresh token. Raises JWTError on any failure."""
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    if payload.get("type") != _REFRESH:
        raise JWTError("Invalid token type")
    return UUID(payload["sub"])
