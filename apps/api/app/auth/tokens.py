import hashlib
import json
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.core.config import get_settings
from app.core.redis import redis_client

settings = get_settings()


class SessionData(BaseModel):
    """Minimal session data stored in Redis.

    Contains only essential identity and temporal bounds.
    Roles and profile data are fetched directly from PostgreSQL on every request
    to ensure role updates, account status changes, and suspensions take immediate effect.
    """

    model_config = ConfigDict(frozen=True)

    user_id: str
    created_at: str
    expires_at: str


def hash_token(raw_token: str) -> str:
    """Compute the SHA-256 hash of a raw session token.

    Only token hashes are used as Redis lookup keys; raw tokens are never persisted.
    """
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def hash_identifier(identifier: str) -> str:
    """Compute SHA-256 hash of a normalized account identifier for privacy-preserving cache keys."""
    return hashlib.sha256(identifier.strip().lower().encode("utf-8")).hexdigest()


def generate_csrf_token() -> str:
    """Generate a cryptographically secure, random CSRF token."""
    return secrets.token_hex(32)


def verify_csrf_token(cookie_token: str | None, header_token: str | None) -> bool:
    """Verify CSRF token using constant-time comparison."""
    if not cookie_token or not header_token:
        return False
    return secrets.compare_digest(cookie_token.strip(), header_token.strip())


async def create_session(user_id: uuid.UUID) -> tuple[str, datetime]:
    """Create a new opaque session token stored securely in Redis.

    Returns:
        tuple[str, datetime]: (raw_token, expires_at)
    """
    raw_token = secrets.token_hex(32)
    token_h = hash_token(raw_token)

    now = datetime.now(UTC)
    ttl_seconds = settings.access_token_expire_minutes * 60
    expires_at = now + timedelta(seconds=ttl_seconds)

    session_payload = SessionData(
        user_id=str(user_id),
        created_at=now.isoformat(),
        expires_at=expires_at.isoformat(),
    )

    redis_key = f"auth:session:{token_h}"
    await redis_client.setex(
        redis_key,
        ttl_seconds,
        session_payload.model_dump_json(),
    )

    return raw_token, expires_at


async def get_session(raw_token: str) -> SessionData | None:
    """Retrieve and validate session data by raw token."""
    if not raw_token:
        return None

    token_h = hash_token(raw_token)
    redis_key = f"auth:session:{token_h}"

    raw_data: Any = await redis_client.get(redis_key)
    if not raw_data:
        return None

    try:
        data_dict = json.loads(raw_data)
        session = SessionData(**data_dict)

        expires_at = datetime.fromisoformat(session.expires_at)
        if datetime.now(UTC) > expires_at:
            await revoke_session(raw_token)
            return None

        return session
    except json.JSONDecodeError, ValueError:
        await revoke_session(raw_token)
        return None


async def revoke_session(raw_token: str) -> bool:
    """Revoke a session by deleting its key from Redis."""
    if not raw_token:
        return False

    token_h = hash_token(raw_token)
    redis_key = f"auth:session:{token_h}"
    deleted = await redis_client.delete(redis_key)
    return bool(deleted > 0)


async def check_login_rate_limit(ip_address: str, normalized_email: str) -> tuple[bool, int]:
    """Check whether authentication failure rate limit is exceeded.

    Returns:
        tuple[bool, int]: (is_allowed, retry_after_seconds)
    """
    # 1. Check IP failure limit
    ip_key = f"auth:ratelimit:ip:{ip_address}"
    ip_count_str = await redis_client.get(ip_key)
    if ip_count_str and int(ip_count_str) >= settings.auth_rate_limit_max_ip_attempts:
        ttl = await redis_client.ttl(ip_key)
        return False, max(int(ttl), 1)

    # 2. Check Account failure limit (using SHA-256 hash of email to protect PII)
    email_h = hash_identifier(normalized_email)
    acct_key = f"auth:ratelimit:account:{email_h}"
    acct_count_str = await redis_client.get(acct_key)
    if acct_count_str and int(acct_count_str) >= settings.auth_rate_limit_max_email_attempts:
        ttl = await redis_client.ttl(acct_key)
        return False, max(int(ttl), 1)

    return True, 0


async def record_login_failure(ip_address: str, normalized_email: str) -> None:
    """Increment failed login counters on IP and account identifier."""
    window = settings.auth_rate_limit_window_seconds

    # 1. Increment IP failure counter
    ip_key = f"auth:ratelimit:ip:{ip_address}"
    ip_count = await redis_client.incr(ip_key)
    if ip_count == 1:
        await redis_client.expire(ip_key, window)

    # 2. Increment Account failure counter (privacy-preserving key)
    email_h = hash_identifier(normalized_email)
    acct_key = f"auth:ratelimit:account:{email_h}"
    acct_count = await redis_client.incr(acct_key)
    if acct_count == 1:
        await redis_client.expire(acct_key, window)


async def reset_account_rate_limit(normalized_email: str) -> None:
    """Reset account failure quota upon successful authentication."""
    email_h = hash_identifier(normalized_email)
    acct_key = f"auth:ratelimit:account:{email_h}"
    await redis_client.delete(acct_key)
