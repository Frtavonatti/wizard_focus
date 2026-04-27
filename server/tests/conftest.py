import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from database import Base, get_db
from main import app

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="session")
async def engine():
    _engine = create_async_engine(TEST_DB_URL, echo=False)
    async with _engine.begin() as conn:
        # Import all models so Base knows about them before create_all
        import models.artifacts  # noqa: F401
        import models.oauth_account  # noqa: F401
        import models.timer_sessions  # noqa: F401
        import models.user  # noqa: F401
        import models.user_stats  # noqa: F401

        await conn.run_sync(Base.metadata.create_all)
    yield _engine
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await _engine.dispose()


@pytest_asyncio.fixture
async def db(engine):
    """Each test gets a transaction that is rolled back on teardown — no state leaks."""
    async with engine.connect() as conn:
        await conn.begin()
        async with AsyncSession(conn, expire_on_commit=False) as session:
            yield session
        await conn.rollback()


@pytest_asyncio.fixture
async def client(db):
    app.dependency_overrides[get_db] = lambda: db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VALID_USER = {"email": "wizard@example.com", "username": "merlin", "password": "Spell$123"}


async def register_user(client: AsyncClient, payload: dict = VALID_USER) -> dict:
    """Register a user and return the full JSON response."""
    r = await client.post("/api/auth/register", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


async def auth_headers(client: AsyncClient, payload: dict = VALID_USER) -> dict:
    """Register (or login) and return Bearer headers."""
    data = await register_user(client, payload)
    return {"Authorization": f"Bearer {data['access_token']}"}
