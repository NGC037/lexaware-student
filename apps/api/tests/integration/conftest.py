from collections.abc import AsyncGenerator

import httpx
import pytest_asyncio

from app.core.redis import redis_client
from app.db.session import engine
from app.main import app


@pytest_asyncio.fixture(autouse=True)
async def reset_database_engine():
    """Reset connection pools and flush Redis state between integration tests."""
    await engine.dispose()
    await redis_client.flushdb()
    yield
    await engine.dispose()
    await redis_client.flushdb()
    await redis_client.aclose()


@pytest_asyncio.fixture
async def async_client() -> AsyncGenerator[httpx.AsyncClient]:
    """Yield an async HTTP test client configured for the FastAPI app."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
