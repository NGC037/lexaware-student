"""One-shot, local-only bootstrap for a development administrator.

This module is intentionally not imported by the ASGI application. Run it only
as ``python -m app.dev_admin_bootstrap`` with explicit environment variables.
"""

from __future__ import annotations

import asyncio
import ipaddress
import os
from collections.abc import Mapping

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.password import hash_password, validate_password_strength
from app.auth.schemas import RegisterRequest
from app.core.config import Settings, get_settings
from app.db.models import AuditEvent, Role, User, UserCredential, UserRole, UserStatus
from app.db.session import AsyncSessionLocal, engine

_ALLOWED_ENVIRONMENTS = {"development", "local", "demo"}
_REQUIRED_ENVIRONMENT = "DEV_ADMIN_BOOTSTRAP_ENABLED"
_CREDENTIAL_ENVIRONMENT = (
    "DEV_ADMIN_EMAIL",
    "DEV_ADMIN_DISPLAY_NAME",
    "DEV_ADMIN_PASSWORD",
)


def _validate_local_bootstrap(settings: Settings, environ: Mapping[str, str]) -> None:
    environment = settings.environment.strip().casefold()
    if environment == "production" or environment not in _ALLOWED_ENVIRONMENTS:
        raise ValueError("Development administrator bootstrap is disabled in this environment.")
    if environ.get(_REQUIRED_ENVIRONMENT, "").strip().casefold() != "true":
        raise ValueError("Set DEV_ADMIN_BOOTSTRAP_ENABLED=true to run this one-shot command.")

    host = settings.postgres_host.strip().casefold()
    if host not in {"localhost", "localhost."}:
        try:
            if not ipaddress.ip_address(host).is_loopback:
                raise ValueError
        except ValueError:
            raise ValueError(
                "Development administrator bootstrap requires a local PostgreSQL host."
            ) from None


def _read_credentials(environ: Mapping[str, str]) -> tuple[str, str, str]:
    values = {name: environ.get(name, "") for name in _CREDENTIAL_ENVIRONMENT}
    missing = [name for name, value in values.items() if not value.strip()]
    if missing:
        raise ValueError("Required development administrator environment variables are missing.")

    email = values["DEV_ADMIN_EMAIL"].strip()
    display_name = values["DEV_ADMIN_DISPLAY_NAME"].strip()
    password = values["DEV_ADMIN_PASSWORD"]
    try:
        payload = RegisterRequest(
            email=email,
            display_name=display_name,
            password=password,
        )
        validate_password_strength(password)
    except ValidationError, ValueError:
        raise ValueError(
            "Administrator details are invalid or the password does not meet account policy."
        ) from None

    if not display_name or len(display_name) > 200:
        raise ValueError("Administrator display name must contain 1 to 200 characters.")
    return str(payload.email).strip().lower(), display_name, password


async def _find_credential(db: AsyncSession, email: str) -> UserCredential | None:
    result = await db.execute(
        select(UserCredential)
        .where(UserCredential.email == email)
        .options(
            selectinload(UserCredential.user).selectinload(User.roles).selectinload(UserRole.role)
        )
    )
    return result.scalar_one_or_none()


async def _create_admin(db: AsyncSession, email: str, display_name: str, password: str) -> bool:
    """Create an admin identity, returning False if the same active admin exists."""
    existing = await _find_credential(db, email)
    if existing is not None:
        roles = {user_role.role.name for user_role in existing.user.roles}
        if "admin" in roles and existing.user.status == UserStatus.ACTIVE:
            return False
        raise ValueError("That email is already assigned to a non-admin or inactive account.")

    role = await db.scalar(select(Role).where(Role.name == "admin"))
    if role is None:
        role = Role(name="admin", description="Administrator role")
        db.add(role)
        await db.flush()

    user = User(display_name=display_name, status=UserStatus.ACTIVE)
    db.add(user)
    await db.flush()
    db.add(
        UserCredential(
            user_id=user.id,
            email=email,
            password_hash=hash_password(password),
        )
    )
    db.add(UserRole(user_id=user.id, role_id=role.id))
    db.add(
        AuditEvent(
            action="auth.dev_admin_bootstrapped",
            resource_type="user",
            resource_id=user.id,
            details={"environment": "local-development", "method": "explicit-cli"},
        )
    )
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        existing = await _find_credential(db, email)
        if (
            existing is not None
            and existing.user.status == UserStatus.ACTIVE
            and any(user_role.role.name == "admin" for user_role in existing.user.roles)
        ):
            return False
        raise ValueError("Administrator creation conflicted with an existing account.") from None
    return True


async def _run() -> None:
    settings = get_settings()
    _validate_local_bootstrap(settings, os.environ)
    email, display_name, password = _read_credentials(os.environ)
    try:
        async with AsyncSessionLocal() as db:
            created = await _create_admin(db, email, display_name, password)
    except SQLAlchemyError:
        raise RuntimeError("Could not complete the local administrator bootstrap.") from None
    finally:
        await engine.dispose()

    print(
        "Local development administrator created."
        if created
        else "The configured active administrator already exists; no changes were made."
    )


def main() -> None:
    try:
        asyncio.run(_run())
    except (ValueError, RuntimeError) as exc:
        raise SystemExit(str(exc)) from None


if __name__ == "__main__":
    main()
