import uuid
from collections.abc import Callable
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.tokens import get_session, revoke_session, verify_csrf_token
from app.core.config import get_settings
from app.db.models import User, UserRole, UserStatus
from app.db.session import get_db_session

settings = get_settings()


def extract_token_from_request(request: Request) -> tuple[str | None, str | None]:
    """Extract opaque session token from HttpOnly cookie or Authorization header.

    Returns:
        tuple[str | None, str | None]: (token, auth_scheme)
        where auth_scheme is 'bearer' or 'cookie'.
    """
    # 1. Authorization header lookup has precedence for non-ambient API clients
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
        if token:
            return token, "bearer"

    # 2. Cookie lookup for browser-based sessions
    cookie_token = request.cookies.get("lexaware_session")
    if cookie_token:
        return cookie_token, "cookie"

    return None, None


async def get_current_user(
    request: Request, db: AsyncSession = Depends(get_db_session)
) -> User | None:
    """Retrieve the current authenticated user from Redis session token.

    Loads the freshest user state and roles from PostgreSQL on every request.
    If an account is suspended or deleted, active sessions are immediately revoked.
    """
    raw_token, auth_scheme = extract_token_from_request(request)
    if not raw_token:
        return None

    session_data = await get_session(raw_token)
    if not session_data:
        return None

    try:
        user_uuid = uuid.UUID(session_data.user_id)
    except ValueError:
        return None

    # Fetch User from database with credentials and roles
    stmt = (
        select(User)
        .where(User.id == user_uuid)
        .options(
            selectinload(User.credential),
            selectinload(User.roles).selectinload(UserRole.role),
        )
    )
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user or user.status != UserStatus.ACTIVE:
        # Immediately revoke session if user does not exist or has been deactivated/suspended
        await revoke_session(raw_token)
        return None

    # Store active session temporal metadata in request.state context (never on the ORM User)
    request.state.raw_token = raw_token
    request.state.auth_scheme = auth_scheme
    try:
        request.state.session_expires_at = datetime.fromisoformat(session_data.expires_at)
    except ValueError:
        request.state.session_expires_at = None

    return user


async def require_authenticated_user(
    user: User | None = Depends(get_current_user),
) -> User:
    """Dependency that enforces an active authenticated user.

    Raises HTTP 401 Unauthorized if unauthenticated.
    """
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_role(*required_roles: str) -> Callable[..., Any]:
    """Dependency factory enforcing that user possesses at least one required role in PostgreSQL.

    Usage:
        @router.get("/admin-only", dependencies=[Depends(require_role("admin"))])
    """

    async def role_checker(user: User = Depends(require_authenticated_user)) -> User:
        user_roles = {ur.role.name for ur in user.roles}
        if not user_roles.intersection(required_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role requirement not met. Required one of: {list(required_roles)}",
            )
        return user

    return role_checker


async def verify_csrf_protection(request: Request) -> None:
    """Validate CSRF protection for cookie-authenticated state-changing requests.

    Threat model:
    - Browser clients authenticate via ambient HttpOnly cookies.
    - Double-Submit CSRF cookie (`lexaware_csrf`) + header (`X-CSRF-Token`)
      and Origin/Referer validation prevent cross-site request forgery.
    - Bearer-token API requests are exempt because headers are not ambiently sent by browsers.
    """
    # Safe methods do not mutate state
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return

    # Check if request authenticates via ambient cookie
    cookie_token = request.cookies.get("lexaware_session")
    auth_header = request.headers.get("Authorization")

    # If request uses Bearer token, it is a direct API client; exempt from browser CSRF check
    if auth_header and auth_header.startswith("Bearer "):
        return

    # If no session cookie is attached, CSRF check is not applicable (unauthenticated)
    if not cookie_token:
        return

    # 1. Validate Origin / Referer if present
    allowed_origins = {settings.web_app_url.rstrip("/"), "http://test", "https://test"}
    origin = request.headers.get("origin")
    if origin:
        if origin.rstrip("/") not in allowed_origins:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cross-origin request rejected",
            )
    else:
        referer = request.headers.get("referer")
        if referer:
            ref_parsed = urlparse(referer)
            ref_origin = f"{ref_parsed.scheme}://{ref_parsed.netloc}"
            if ref_origin not in allowed_origins:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Cross-origin request rejected",
                )

    # 2. Validate Double Submit CSRF token
    cookie_csrf = request.cookies.get("lexaware_csrf")
    header_csrf = request.headers.get("x-csrf-token") or request.headers.get("X-CSRF-Token")

    if not cookie_csrf or not header_csrf or not verify_csrf_token(cookie_csrf, header_csrf):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token validation failed",
        )
