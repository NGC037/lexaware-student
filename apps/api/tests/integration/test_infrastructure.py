from sqlalchemy import text

from app.core.redis import redis_client
from app.db.session import engine


async def test_postgresql_connectivity() -> None:
    async with engine.connect() as connection:
        result = await connection.execute(text("SELECT current_user, current_database()"))
        user, database = result.one()

    assert user == "lexaware"
    assert database == "lexaware"


async def test_redis_connectivity() -> None:
    assert await redis_client.ping() is True


async def test_alembic_and_pgvector_state() -> None:
    async with engine.connect() as connection:
        revision_result = await connection.execute(text("SELECT version_num FROM alembic_version"))
        extension_result = await connection.execute(
            text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
        )
        revision = revision_result.scalar_one()
        extension_version = extension_result.scalar_one()

    assert revision == "19bffc3ace56"
    assert extension_version
