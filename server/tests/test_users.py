from httpx import AsyncClient

from tests.conftest import VALID_USER, auth_headers, register_user


class TestGetMe:
    async def test_returns_profile(self, client: AsyncClient):
        headers = await auth_headers(client)
        r = await client.get("/api/users/me", headers=headers)
        assert r.status_code == 200
        body = r.json()
        assert body["email"] == VALID_USER["email"]
        assert body["username"] == VALID_USER["username"]
        assert "id" in body
        assert "created_at" in body
        assert "hashed_password" not in body

    async def test_no_token_is_401(self, client: AsyncClient):
        r = await client.get("/api/users/me")
        assert r.status_code == 401

    async def test_invalid_token_is_401(self, client: AsyncClient):
        r = await client.get("/api/users/me", headers={"Authorization": "Bearer garbage"})
        assert r.status_code == 401


class TestUpdateMe:
    async def test_update_username(self, client: AsyncClient):
        headers = await auth_headers(client)
        r = await client.patch("/api/users/me", json={"username": "gandalf"}, headers=headers)
        assert r.status_code == 200
        assert r.json()["username"] == "gandalf"

    async def test_update_email(self, client: AsyncClient):
        headers = await auth_headers(client)
        r = await client.patch(
            "/api/users/me",
            json={"email": "new@example.com"},
            headers=headers,
        )
        assert r.status_code == 200
        assert r.json()["email"] == "new@example.com"

    async def test_update_password_does_not_expose_hash(self, client: AsyncClient):
        headers = await auth_headers(client)
        r = await client.patch(
            "/api/users/me",
            json={"password": "NewSpell$456"},
            headers=headers,
        )
        assert r.status_code == 200
        assert "hashed_password" not in r.json()

    async def test_empty_body_is_noop(self, client: AsyncClient):
        headers = await auth_headers(client)
        r = await client.patch("/api/users/me", json={}, headers=headers)
        assert r.status_code == 200
        assert r.json()["username"] == VALID_USER["username"]

    async def test_duplicate_email_is_409(self, client: AsyncClient):
        other = {"email": "other@example.com", "username": "otherguy", "password": "Pass$123"}
        await register_user(client, other)
        headers = await auth_headers(client)
        r = await client.patch(
            "/api/users/me",
            json={"email": other["email"]},
            headers=headers,
        )
        assert r.status_code == 409

    async def test_duplicate_username_is_409(self, client: AsyncClient):
        other = {"email": "other2@example.com", "username": "otherguy2", "password": "Pass$123"}
        await register_user(client, other)
        headers = await auth_headers(client)
        r = await client.patch(
            "/api/users/me",
            json={"username": other["username"]},
            headers=headers,
        )
        assert r.status_code == 409

    async def test_no_token_is_401(self, client: AsyncClient):
        r = await client.patch("/api/users/me", json={"username": "x"})
        assert r.status_code == 401

    async def test_null_email_is_noop(self, client: AsyncClient):
        headers = await auth_headers(client)
        r = await client.patch("/api/users/me", json={"email": None}, headers=headers)
        assert r.status_code == 200
        assert r.json()["email"] == VALID_USER["email"]

    async def test_null_username_is_noop(self, client: AsyncClient):
        headers = await auth_headers(client)
        r = await client.patch("/api/users/me", json={"username": None}, headers=headers)
        assert r.status_code == 200
        assert r.json()["username"] == VALID_USER["username"]

    async def test_null_password_is_noop(self, client: AsyncClient):
        headers = await auth_headers(client)
        r = await client.patch("/api/users/me", json={"password": None}, headers=headers)
        assert r.status_code == 200


class TestDeleteMe:
    async def test_delete_returns_204(self, client: AsyncClient):
        headers = await auth_headers(client)
        r = await client.delete("/api/users/me", headers=headers)
        assert r.status_code == 204

    async def test_deleted_token_is_401(self, client: AsyncClient):
        headers = await auth_headers(client)
        await client.delete("/api/users/me", headers=headers)
        r = await client.get("/api/users/me", headers=headers)
        assert r.status_code == 401

    async def test_no_token_is_401(self, client: AsyncClient):
        r = await client.delete("/api/users/me")
        assert r.status_code == 401
