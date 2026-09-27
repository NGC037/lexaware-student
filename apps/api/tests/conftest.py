"""Provision disposable, isolated backing services for integration test runs."""

from __future__ import annotations

import asyncio
import os
import uuid
import warnings
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlparse

import asyncpg  # type: ignore[import-untyped]
import boto3
import pytest
from alembic.config import Config
from botocore.config import Config as BotoConfig

from alembic import command
from app.core.config import Settings

API_ROOT = Path(__file__).resolve().parents[1]
_run_id = uuid.uuid4().hex[:12]
_test_database = f"lexaware_test_{_run_id}"
_test_bucket = f"lexaware-test-{_run_id}"
_state: dict[str, object] = {}
_settings = Settings()

if _settings.environment.lower() == "production":
    raise RuntimeError("Integration tests cannot run against a production environment.")
if _settings.postgres_host.lower() not in {"localhost", "127.0.0.1", "::1"}:
    raise RuntimeError("Integration tests require a local PostgreSQL host.")
if _settings.redis_db == 15:
    raise RuntimeError("Redis database 15 is reserved for integration tests.")
_storage_host = urlparse(_settings.s3_endpoint).hostname
if _storage_host not in {"localhost", "127.0.0.1", "::1"}:
    raise RuntimeError("Integration tests require a local object-storage endpoint.")

# Set these before child conftests import app.main, app.db.session, or Redis.
os.environ["ENVIRONMENT"] = "test"
os.environ["POSTGRES_DB"] = _test_database
os.environ["REDIS_DB"] = "15"
os.environ["S3_BUCKET"] = _test_bucket
_state["settings"] = _settings


def _needs_integration_services(config: pytest.Config) -> bool:
    args = [str(argument).replace("\\", "/").lower() for argument in config.args]
    if not args:
        return True
    return any(
        "integration" in argument or argument.rstrip("/").endswith("tests") for argument in args
    )


async def _create_test_database(settings: Settings) -> None:
    connection = await asyncpg.connect(
        host=settings.postgres_host,
        port=settings.postgres_port,
        user=settings.postgres_user,
        password=settings.postgres_password,
        database="postgres",
        timeout=10,
    )
    try:
        exists = await connection.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1", _test_database
        )
        if exists:
            raise RuntimeError(f"Disposable test database {_test_database} unexpectedly exists.")
        await connection.execute(f'CREATE DATABASE "{_test_database}"')
    finally:
        await connection.close()


def _storage_client(settings: Settings) -> Any:
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint,
        region_name=settings.s3_region,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        config=BotoConfig(signature_version="s3v4", connect_timeout=5, read_timeout=30),
    )


def _ensure_test_bucket(settings: Settings) -> None:
    client = _storage_client(settings)
    client.create_bucket(Bucket=_test_bucket)
    _state["storage_client"] = client


def pytest_configure(config: pytest.Config) -> None:
    """Point all imported application clients at test-only infrastructure."""
    _state["needs_services"] = _needs_integration_services(config)


def pytest_sessionstart(session: pytest.Session) -> None:
    """Create a fresh database/schema and object bucket before app imports."""
    if not _state.get("needs_services"):
        return

    settings = _settings
    try:
        asyncio.run(_create_test_database(settings))
        _state["database_created"] = True
        config = Config(str(API_ROOT / "alembic.ini"))
        command.upgrade(config, "head")
        _ensure_test_bucket(settings)
    except Exception as exc:
        raise pytest.UsageError(
            "Could not provision isolated integration-test services. Check local PostgreSQL "
            "and MinIO credentials; the configured development database was not modified."
        ) from exc


def _drop_test_database(settings: Settings) -> None:
    async def drop() -> None:
        connection = await asyncpg.connect(
            host=settings.postgres_host,
            port=settings.postgres_port,
            user=settings.postgres_user,
            password=settings.postgres_password,
            database="postgres",
            timeout=10,
        )
        try:
            await connection.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = $1 AND pid <> pg_backend_pid()",
                _test_database,
            )
            await connection.execute(f'DROP DATABASE IF EXISTS "{_test_database}"')
        finally:
            await connection.close()

    asyncio.run(drop())


def _drop_test_bucket() -> None:
    client = cast(Any, _state.get("storage_client"))
    if client is None:
        return
    for page in client.get_paginator("list_objects_v2").paginate(Bucket=_test_bucket):
        objects = [{"Key": item["Key"]} for item in page.get("Contents", [])]
        if objects:
            client.delete_objects(Bucket=_test_bucket, Delete={"Objects": objects})
    client.delete_bucket(Bucket=_test_bucket)


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Remove only this run's generated test database and object bucket."""
    if not _state.get("database_created"):
        return
    settings = _state["settings"]
    assert isinstance(settings, Settings)
    try:
        from app.db.session import engine

        asyncio.run(engine.dispose())
        _drop_test_database(settings)
        _drop_test_bucket()
    except Exception as exc:
        warnings.warn(
            f"Could not remove disposable test resources for run {_run_id}: {exc}",
            RuntimeWarning,
            stacklevel=2,
        )
