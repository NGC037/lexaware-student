from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


async def check_database_connection(engine: AsyncEngine) -> bool:
    """Check whether PostgreSQL is reachable."""
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
