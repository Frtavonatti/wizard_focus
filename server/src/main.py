from fastapi import FastAPI
from sqlalchemy import text

from config import settings
from database import AsyncSessionLocal
from routers import auth, stats, users

app = FastAPI(title="Wizard Focus API")

app.include_router(auth.router, prefix=settings.API_PREFIX)
app.include_router(users.router, prefix=settings.API_PREFIX)
app.include_router(stats.router, prefix=settings.API_PREFIX)


@app.get("/")
async def root():
    return {"message": "Wizard Focus API is running"}


@app.get("/health")
async def health_check():
    from fastapi import Response
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception:
        return Response(
            content='{"status":"error","database":"unavailable"}',
            status_code=503,
            media_type="application/json",
        )
