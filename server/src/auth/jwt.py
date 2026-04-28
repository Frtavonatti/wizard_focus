from datetime import datetime, timedelta, timezone
from uuid import UUID

from jose import JWTError, jwt

from config import get_settings

_ACCESS = "access"
_REFRESH = "refresh"


def _make_token(subject: UUID, token_type: str, expires_delta: timedelta) -> str:
    s = get_settings()
    expire = datetime.now(timezone.utc) + expires_delta
    payload = {"sub": str(subject), "type": token_type, "exp": expire}
    return jwt.encode(payload, s.SECRET_KEY, algorithm=s.JWT_ALGORITHM)


def create_access_token(user_id: UUID) -> str:
    return _make_token(
        user_id,
        _ACCESS,
        timedelta(minutes=get_settings().ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def create_refresh_token(user_id: UUID) -> str:
    return _make_token(
        user_id,
        _REFRESH,
        timedelta(days=get_settings().REFRESH_TOKEN_EXPIRE_DAYS),
    )


def decode_access_token(token: str) -> UUID:
    """Decode and validate an access token. Raises JWTError on any failure."""
    s = get_settings()
    payload = jwt.decode(token, s.SECRET_KEY, algorithms=[s.JWT_ALGORITHM])
    if payload.get("type") != _ACCESS:
        raise JWTError("Invalid token type")
    try:
        return UUID(payload["sub"])
    except (ValueError, KeyError) as exc:
        raise JWTError("Invalid subject claim") from exc


def decode_refresh_token(token: str) -> UUID:
    """Decode and validate a refresh token. Raises JWTError on any failure."""
    s = get_settings()
    payload = jwt.decode(token, s.SECRET_KEY, algorithms=[s.JWT_ALGORITHM])
    if payload.get("type") != _REFRESH:
        raise JWTError("Invalid token type")
    try:
        return UUID(payload["sub"])
    except (ValueError, KeyError) as exc:
        raise JWTError("Invalid subject claim") from exc
