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
    """Session data stored in Redis.

    Contains only non-sensitive identity metadata needed for request authentication.
    Internal details like token hashes or Redis keys are never exposed.
    """

    model_config = ConfigDict(frozen=True)

    user_id: str
    roles: list[str]
    created_at: str
    expires_at: str


def hash_token(raw_token: str) -> str:
    """Compute the SHA-256 hash of a raw session token.

    Only token hashes are used as Redis lookup keys; raw tokens are never persisted.
    """
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


async def create_session(user_id: uuid.UUID, roles: list[str]) -> tuple[str, datetime]:
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
        roles=roles,
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


async def check_rate_limit(ip_address: str, normalized_email: str | None = None) -> bool:
    """Check layered authentication rate limits for IP and account identifier.

    Returns True if allowed, False if limit exceeded.
    """
    window = settings.auth_rate_limit_window_seconds

    # 1. IP-based rate limit
    ip_key = f"auth:ratelimit:ip:{ip_address}"
    ip_count = await redis_client.incr(ip_key)
    if ip_count == 1:
        await redis_client.expire(ip_key, window)

    if ip_count > settings.auth_rate_limit_max_ip_attempts:
        return False

    # 2. Email-based rate limit (if provided)
    if normalized_email:
        email_key = f"auth:ratelimit:email:{normalized_email}"
        email_count = await redis_client.incr(email_key)
        if email_count == 1:
            await redis_client.expire(email_key, window)

        if email_count > settings.auth_rate_limit_max_email_attempts:
            return False

    return True
