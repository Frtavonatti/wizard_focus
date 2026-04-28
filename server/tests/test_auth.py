from datetime import datetime, timedelta, timezone

from httpx import AsyncClient
from jose import jwt

from config import get_settings
from tests.conftest import VALID_USER, auth_headers, register_user


def _forge_token(token_type: str, sub: str) -> str:
    """Create a validly-signed token with an arbitrary sub value."""
    payload = {
        "sub": sub,
        "type": token_type,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
    }
    s = get_settings()
    return jwt.encode(payload, s.SECRET_KEY, algorithm=s.JWT_ALGORITHM)


class TestRegister:
    async def test_returns_tokens(self, client: AsyncClient):
        data = await register_user(client)
        assert data["access_token"]
        assert data["refresh_token"]
        assert data["token_type"] == "bearer"

    async def test_creates_stats_row(self, client: AsyncClient):
        headers = await auth_headers(client)
        r = await client.get("/api/stats/me", headers=headers)
        assert r.status_code == 200
        body = r.json()
        assert body["total_sessions"] == 0
        assert body["total_minutes"] == 0

    async def test_duplicate_email_is_409(self, client: AsyncClient):
        await register_user(client)
        r = await client.post(
            "/api/auth/register",
            json={**VALID_USER, "username": "other"},
        )
        assert r.status_code == 409
        assert "Email" in r.json()["detail"]

    async def test_duplicate_username_is_409(self, client: AsyncClient):
        await register_user(client)
        r = await client.post(
            "/api/auth/register",
            json={**VALID_USER, "email": "other@example.com"},
        )
        assert r.status_code == 409
        assert "Username" in r.json()["detail"]

    async def test_invalid_email_is_422(self, client: AsyncClient):
        r = await client.post(
            "/api/auth/register",
            json={"email": "not-an-email", "username": "x", "password": "y"},
        )
        assert r.status_code == 422


class TestLogin:
    async def test_valid_credentials_return_tokens(self, client: AsyncClient):
        await register_user(client)
        r = await client.post(
            "/api/auth/login",
            json={"email": VALID_USER["email"], "password": VALID_USER["password"]},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["access_token"]
        assert data["refresh_token"]

    async def test_wrong_password_is_401(self, client: AsyncClient):
        await register_user(client)
        r = await client.post(
            "/api/auth/login",
            json={"email": VALID_USER["email"], "password": "wrongpass"},
        )
        assert r.status_code == 401

    async def test_unknown_email_is_401(self, client: AsyncClient):
        r = await client.post(
            "/api/auth/login",
            json={"email": "ghost@example.com", "password": "anything"},
        )
        assert r.status_code == 401

    async def test_non_uuid_sub_access_token_is_401(self, client: AsyncClient):
        token = _forge_token("access", "not-a-uuid")
        r = await client.get("/api/users/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 401


class TestRefresh:
    async def test_valid_refresh_returns_new_tokens(self, client: AsyncClient):
        data = await register_user(client)
        r = await client.post(
            "/api/auth/refresh",
            json={"refresh_token": data["refresh_token"]},
        )
        assert r.status_code == 200
        new_data = r.json()
        assert new_data["access_token"]
        assert new_data["refresh_token"]

    async def test_garbage_token_is_401(self, client: AsyncClient):
        r = await client.post(
            "/api/auth/refresh",
            json={"refresh_token": "not.a.token"},
        )
        assert r.status_code == 401

    async def test_access_token_rejected_as_refresh(self, client: AsyncClient):
        data = await register_user(client)
        r = await client.post(
            "/api/auth/refresh",
            json={"refresh_token": data["access_token"]},
        )
        assert r.status_code == 401

    async def test_non_uuid_sub_refresh_token_is_401(self, client: AsyncClient):
        token = _forge_token("refresh", "not-a-uuid")
        r = await client.post("/api/auth/refresh", json={"refresh_token": token})
        assert r.status_code == 401


class TestLogout:
    async def test_logout_returns_200(self, client: AsyncClient):
        r = await client.post("/api/auth/logout")
        assert r.status_code == 200
