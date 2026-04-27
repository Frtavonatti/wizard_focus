import pytest
from httpx import AsyncClient

from tests.conftest import VALID_USER, auth_headers, register_user


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


class TestLogout:
    async def test_logout_returns_200(self, client: AsyncClient):
        r = await client.post("/api/auth/logout")
        assert r.status_code == 200
