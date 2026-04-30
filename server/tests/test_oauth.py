from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from httpx import AsyncClient
from jose import jwt

from config import settings
from tests.conftest import VALID_USER, register_user

_MOCK_GOOGLE_TOKEN_RESPONSE = {"access_token": "google-access-token", "token_type": "Bearer"}
_MOCK_USER_INFO = {
    "sub": "google-uid-123",
    "email": "googleuser@example.com",
    "name": "Google Wizard",
}

_MOCK_GITHUB_TOKEN_RESPONSE = {"access_token": "github-access-token", "token_type": "bearer"}
_MOCK_GITHUB_USER_INFO = {
    "id": 99999,
    "login": "githubwizard",
    "email": "githubuser@example.com",
    "name": "GitHub Wizard",
}


def _make_state_cookie(state: str) -> str:
    """Create a validly-signed state cookie containing the given raw state."""
    return jwt.encode(
        {
            "state": state,
            "type": "oauth_state",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=10),
        },
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


async def _do_oauth_callback(
    client: AsyncClient,
    provider: str,
    state: str,
    code: str = "auth-code",
    state_cookie: str | None = None,
) -> httpx.Response:
    cookie = state_cookie if state_cookie is not None else _make_state_cookie(state)
    client.cookies.set("oauth_state", cookie)
    return await client.get(
        f"/api/auth/{provider}/callback?code={code}&state={state}",
        follow_redirects=False,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestGoogleLogin:
    async def test_redirects_to_google(self, client: AsyncClient, monkeypatch):
        monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "test-google-client-id")
        r = await client.get("/api/auth/google", follow_redirects=False)
        assert r.status_code in (302, 307)
        assert "accounts.google.com" in r.headers["location"]

    async def test_sets_httponly_state_cookie(self, client: AsyncClient, monkeypatch):
        monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "test-google-client-id")
        r = await client.get("/api/auth/google", follow_redirects=False)
        set_cookie = r.headers.get("set-cookie", "")
        assert "oauth_state" in set_cookie
        assert "httponly" in set_cookie.lower()


class TestUnknownProvider:
    async def test_unknown_provider_login_is_422(self, client: AsyncClient):
        r = await client.get("/api/auth/twitter", follow_redirects=False)
        assert r.status_code == 422

    async def test_unknown_provider_callback_is_422(self, client: AsyncClient):
        r = await client.get("/api/auth/twitter/callback?code=x&state=y", follow_redirects=False)
        assert r.status_code == 422


class TestGoogleCallback:
    async def test_new_user_created_and_redirected_with_tokens(self, client: AsyncClient):
        state = "some-state-value"
        with (
            pytest.MonkeyPatch().context() as mp,
        ):
            mp.setattr("routers.oauth.exchange_google_code", AsyncMock(return_value=_MOCK_GOOGLE_TOKEN_RESPONSE))
            mp.setattr("routers.oauth.get_google_user_info", AsyncMock(return_value=_MOCK_USER_INFO))
            r = await _do_oauth_callback(client, "google", state)

        assert r.status_code in (302, 307)
        location = r.headers["location"]
        assert "code=" in location
        assert "access_token=" not in location
        assert "refresh_token=" not in location

    async def test_existing_oauth_user_reused(self, client: AsyncClient):
        """Second login with same Google account links to the same user."""
        state = "some-state-value"
        with (
            pytest.MonkeyPatch().context() as mp,
        ):
            mp.setattr("routers.oauth.exchange_google_code", AsyncMock(return_value=_MOCK_GOOGLE_TOKEN_RESPONSE))
            mp.setattr("routers.oauth.get_google_user_info", AsyncMock(return_value=_MOCK_USER_INFO))
            r1 = await _do_oauth_callback(client, "google", state, code="code-first")
            r2 = await _do_oauth_callback(client, "google", state, code="code-second")

        assert r1.status_code in (302, 307)
        assert r2.status_code in (302, 307)

    async def test_existing_password_account_gets_linked(self, client: AsyncClient):
        """OAuth login with an email that already has a password account links them."""
        existing = {**VALID_USER, "email": _MOCK_USER_INFO["email"]}
        await register_user(client, existing)

        state = "some-state-value"
        with pytest.MonkeyPatch().context() as mp:
            mp.setattr("routers.oauth.exchange_google_code", AsyncMock(return_value=_MOCK_GOOGLE_TOKEN_RESPONSE))
            mp.setattr("routers.oauth.get_google_user_info", AsyncMock(return_value=_MOCK_USER_INFO))
            r = await _do_oauth_callback(client, "google", state)

        assert r.status_code in (302, 307)
        assert "code=" in r.headers["location"]

    async def test_missing_code_is_400(self, client: AsyncClient):
        state = "some-state-value"
        client.cookies.set("oauth_state", _make_state_cookie(state))
        r = await client.get(f"/api/auth/google/callback?state={state}", follow_redirects=False)
        assert r.status_code == 400

    async def test_missing_state_cookie_is_400(self, client: AsyncClient):
        r = await client.get(
            "/api/auth/google/callback?code=x&state=y", follow_redirects=False
        )
        assert r.status_code == 400

    async def test_mismatched_state_is_400(self, client: AsyncClient):
        client.cookies.set("oauth_state", _make_state_cookie("expected-state"))
        r = await client.get(
            "/api/auth/google/callback?code=x&state=different-state",
            follow_redirects=False,
        )
        assert r.status_code == 400

    async def test_google_token_exchange_error_is_400(self, client: AsyncClient):
        state = "some-state-value"
        mock_error = httpx.HTTPStatusError(
            "error", request=MagicMock(), response=MagicMock(status_code=400)
        )
        with pytest.MonkeyPatch().context() as mp:
            mp.setattr("routers.oauth.exchange_google_code", AsyncMock(side_effect=mock_error))
            r = await _do_oauth_callback(client, "google", state)
        assert r.status_code == 400

    async def test_google_userinfo_error_is_400(self, client: AsyncClient):
        state = "some-state-value"
        mock_error = httpx.HTTPStatusError(
            "error", request=MagicMock(), response=MagicMock(status_code=401)
        )
        with pytest.MonkeyPatch().context() as mp:
            mp.setattr("routers.oauth.exchange_google_code", AsyncMock(return_value=_MOCK_GOOGLE_TOKEN_RESPONSE))
            mp.setattr("routers.oauth.get_google_user_info", AsyncMock(side_effect=mock_error))
            r = await _do_oauth_callback(client, "google", state)
        assert r.status_code == 400

    async def test_oauth_error_param_is_400(self, client: AsyncClient):
        state = "some-state-value"
        client.cookies.set("oauth_state", _make_state_cookie(state))
        r = await client.get(
            f"/api/auth/google/callback?error=access_denied&state={state}",
            follow_redirects=False,
        )
        assert r.status_code == 400

    async def test_missing_email_in_userinfo_is_400(self, client: AsyncClient):
        state = "some-state-value"
        user_info_no_email = {**_MOCK_USER_INFO, "email": None}
        with pytest.MonkeyPatch().context() as mp:
            mp.setattr("routers.oauth.exchange_google_code", AsyncMock(return_value=_MOCK_GOOGLE_TOKEN_RESPONSE))
            mp.setattr(
                "routers.oauth.get_google_user_info",
                AsyncMock(return_value=user_info_no_email),
            )
            r = await _do_oauth_callback(client, "google", state)
        assert r.status_code == 400


class TestGithubLogin:
    async def test_redirects_to_github(self, client: AsyncClient, monkeypatch):
        monkeypatch.setattr(settings, "GITHUB_CLIENT_ID", "test-github-client-id")
        r = await client.get("/api/auth/github", follow_redirects=False)
        assert r.status_code in (302, 307)
        assert "github.com" in r.headers["location"]

    async def test_sets_httponly_state_cookie(self, client: AsyncClient, monkeypatch):
        monkeypatch.setattr(settings, "GITHUB_CLIENT_ID", "test-github-client-id")
        r = await client.get("/api/auth/github", follow_redirects=False)
        set_cookie = r.headers.get("set-cookie", "")
        assert "oauth_state" in set_cookie
        assert "httponly" in set_cookie.lower()


class TestGithubCallback:
    async def test_new_user_created_and_redirected_with_tokens(self, client: AsyncClient):
        state = "some-state-value"
        with pytest.MonkeyPatch().context() as mp:
            mp.setattr("routers.oauth.exchange_github_code", AsyncMock(return_value=_MOCK_GITHUB_TOKEN_RESPONSE))
            mp.setattr("routers.oauth.get_github_user_info", AsyncMock(return_value=_MOCK_GITHUB_USER_INFO))
            r = await _do_oauth_callback(client, "github", state)

        assert r.status_code in (302, 307)
        location = r.headers["location"]
        assert "code=" in location
        assert "access_token=" not in location
        assert "refresh_token=" not in location

    async def test_existing_oauth_user_reused(self, client: AsyncClient):
        state = "some-state-value"
        with pytest.MonkeyPatch().context() as mp:
            mp.setattr("routers.oauth.exchange_github_code", AsyncMock(return_value=_MOCK_GITHUB_TOKEN_RESPONSE))
            mp.setattr("routers.oauth.get_github_user_info", AsyncMock(return_value=_MOCK_GITHUB_USER_INFO))
            r1 = await _do_oauth_callback(client, "github", state, code="code-first")
            r2 = await _do_oauth_callback(client, "github", state, code="code-second")

        assert r1.status_code in (302, 307)
        assert r2.status_code in (302, 307)

    async def test_existing_password_account_gets_linked(self, client: AsyncClient):
        existing = {**VALID_USER, "email": _MOCK_GITHUB_USER_INFO["email"]}
        await register_user(client, existing)

        state = "some-state-value"
        with pytest.MonkeyPatch().context() as mp:
            mp.setattr("routers.oauth.exchange_github_code", AsyncMock(return_value=_MOCK_GITHUB_TOKEN_RESPONSE))
            mp.setattr("routers.oauth.get_github_user_info", AsyncMock(return_value=_MOCK_GITHUB_USER_INFO))
            r = await _do_oauth_callback(client, "github", state)

        assert r.status_code in (302, 307)
        assert "code=" in r.headers["location"]

    async def test_missing_state_cookie_is_400(self, client: AsyncClient):
        r = await client.get(
            "/api/auth/github/callback?code=x&state=y", follow_redirects=False
        )
        assert r.status_code == 400

    async def test_mismatched_state_is_400(self, client: AsyncClient):
        client.cookies.set("oauth_state", _make_state_cookie("expected-state"))
        r = await client.get(
            "/api/auth/github/callback?code=x&state=different-state",
            follow_redirects=False,
        )
        assert r.status_code == 400

    async def test_github_token_exchange_error_is_400(self, client: AsyncClient):
        state = "some-state-value"
        mock_error = httpx.HTTPStatusError(
            "error", request=MagicMock(), response=MagicMock(status_code=400)
        )
        with pytest.MonkeyPatch().context() as mp:
            mp.setattr("routers.oauth.exchange_github_code", AsyncMock(side_effect=mock_error))
            r = await _do_oauth_callback(client, "github", state)
        assert r.status_code == 400

    async def test_missing_email_in_userinfo_is_400(self, client: AsyncClient):
        state = "some-state-value"
        user_info_no_email = {**_MOCK_GITHUB_USER_INFO, "email": None}
        with pytest.MonkeyPatch().context() as mp:
            mp.setattr("routers.oauth.exchange_github_code", AsyncMock(return_value=_MOCK_GITHUB_TOKEN_RESPONSE))
            mp.setattr("routers.oauth.get_github_user_info", AsyncMock(return_value=user_info_no_email))
            r = await _do_oauth_callback(client, "github", state)
        assert r.status_code == 400


class TestTokenExchange:
    async def test_valid_code_returns_tokens(self, client: AsyncClient):
        state = "some-state-value"
        with pytest.MonkeyPatch().context() as mp:
            mp.setattr("routers.oauth.exchange_google_code", AsyncMock(return_value=_MOCK_GOOGLE_TOKEN_RESPONSE))
            mp.setattr("routers.oauth.get_google_user_info", AsyncMock(return_value=_MOCK_USER_INFO))
            r = await _do_oauth_callback(client, "google", state)

        assert r.status_code in (302, 307)
        code = r.headers["location"].split("code=")[1]

        r2 = await client.post("/api/auth/token/exchange", json={"code": code})
        assert r2.status_code == 200
        data = r2.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    async def test_invalid_code_is_400(self, client: AsyncClient):
        r = await client.post("/api/auth/token/exchange", json={"code": "not-a-valid-token"})
        assert r.status_code == 400

    async def test_wrong_token_type_is_400(self, client: AsyncClient):
        from datetime import datetime, timedelta, timezone
        from jose import jwt as jose_jwt

        wrong_type_token = jose_jwt.encode(
            {"sub": "00000000-0000-0000-0000-000000000001", "type": "access", "exp": datetime.now(timezone.utc) + timedelta(minutes=1)},
            settings.SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM,
        )
        r = await client.post("/api/auth/token/exchange", json={"code": wrong_type_token})
        assert r.status_code == 400
