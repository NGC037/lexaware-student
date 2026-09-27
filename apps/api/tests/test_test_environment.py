from app.core.config import get_settings
from app.core.redis import redis_client
from app.db.session import engine


def test_pytest_uses_run_scoped_postgres_and_object_storage() -> None:
    settings = get_settings()

    assert settings.postgres_db.startswith("lexaware_test_")
    assert settings.postgres_db != "lexaware"
    assert engine.url.database == settings.postgres_db
    assert settings.redis_db == 15
    assert redis_client.connection_pool.connection_kwargs["db"] == 15
    assert settings.s3_bucket.startswith("lexaware-test-")
