import pytest_asyncio

from app.core.redis import redis_client
from app.db.session import engine


@pytest_asyncio.fixture(autouse=True)
async def reset_database_engine():
    await engine.dispose()
    yield
    await engine.dispose()
    await redis_client.aclose()
