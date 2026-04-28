from httpx import AsyncClient

from tests.conftest import auth_headers


class TestGetMyStats:
    async def test_returns_zeroed_stats_after_register(self, client: AsyncClient):
        headers = await auth_headers(client)
        r = await client.get("/api/stats/me", headers=headers)
        assert r.status_code == 200
        body = r.json()
        assert body["total_sessions"] == 0
        assert body["total_minutes"] == 0
        assert body["current_strike"] == 0
        assert body["longest_strike"] == 0
        assert body["last_session_date"] is None

    async def test_no_token_is_401(self, client: AsyncClient):
        r = await client.get("/api/stats/me")
        assert r.status_code == 401
