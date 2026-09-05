import uuid
from collections.abc import Callable
from typing import Any

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.tokens import get_session
from app.db.models import User, UserRole, UserStatus
from app.db.session import get_db_session


def extract_token_from_request(request: Request) -> str | None:
    """Extract opaque session token from HttpOnly cookie or Authorization header.

    Priority:
    1. Cookie: `lexaware_session`
    2. Header: `Authorization: Bearer <token>`
    """
    # 1. Cookie lookup
    cookie_token = request.cookies.get("lexaware_session")
    if cookie_token:
        return cookie_token

    # 2. Authorization header lookup
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:].strip()

    return None


async def get_current_user(
    request: Request, db: AsyncSession = Depends(get_db_session)
) -> User | None:
    """Retrieve the current authenticated user from Redis session token.

    Returns None if no token is provided, session is expired, or user is inactive.
    """
    raw_token = extract_token_from_request(request)
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
        return None

    user._raw_token = raw_token
    user._session_expires_at = session_data.expires_at
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
    """Dependency factory enforcing that user possesses at least one required role.

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
