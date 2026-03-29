from fastapi import FastAPI
from sqlalchemy import text

from database import AsyncSessionLocal

app = FastAPI(title="Wizard Focus API")


@app.get("/")
async def root():
    return {"message": "Wizard Focus API is running"}


@app.get("/health")
async def health_check():
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        return {"status": "error", "database": str(e)}
