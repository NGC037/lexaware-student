from redis.asyncio import Redis

from app.core.config import get_settings

settings = get_settings()

redis_client: Redis = Redis(
    host=settings.redis_host,
    port=settings.redis_port,
    decode_responses=True,
)


async def check_redis_connection() -> bool:
    """Check whether Redis is reachable."""
    try:
        return bool(await redis_client.ping())
    except Exception:
        return False


async def close_redis_connection() -> None:
    """Close the Redis client cleanly."""
    await redis_client.aclose()
