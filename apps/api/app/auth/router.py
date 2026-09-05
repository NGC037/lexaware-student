from datetime import datetime

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import (
    extract_token_from_request,
    get_current_user,
    require_authenticated_user,
)
from app.auth.schemas import (
    LoginRequest,
    MeResponse,
    MessageResponse,
    RegisterRequest,
    UserResponse,
)
from app.auth.service import authenticate_user, logout_user, register_user
from app.core.config import get_settings
from app.db.models import User
from app.db.session import get_db_session

settings = get_settings()

auth_router = APIRouter(prefix="/auth", tags=["authentication"])


def set_session_cookie(response: Response, raw_token: str) -> None:
    """Set the secure HttpOnly session cookie on an HTTP response."""
    max_age_seconds = settings.access_token_expire_minutes * 60
    response.set_cookie(
        key="lexaware_session",
        value=raw_token,
        max_age=max_age_seconds,
        httponly=True,
        secure=settings.is_production,
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    """Clear the session cookie from an HTTP response."""
    response.delete_cookie(
        key="lexaware_session",
        path="/",
        httponly=True,
        secure=settings.is_production,
        samesite="lax",
    )


@auth_router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new student account",
)
async def register(
    req: RegisterRequest,
    db: AsyncSession = Depends(get_db_session),
) -> UserResponse:
    """Register a new user account with email and password."""
    user, email, roles = await register_user(db, req)
    return UserResponse(
        id=user.id,
        email=email,
        display_name=user.display_name,
        roles=roles,
        status=user.status.value,
    )


@auth_router.post(
    "/login",
    response_model=UserResponse,
    summary="Authenticate and establish a secure session",
)
async def login(
    req: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
) -> UserResponse:
    """Authenticate email and password, returning an HttpOnly session cookie."""
    client_ip = request.client.host if request.client else "127.0.0.1"

    user, email, roles, raw_token, _expires_at = await authenticate_user(
        db, email=req.email, password=req.password, ip_address=client_ip
    )

    set_session_cookie(response, raw_token)

    return UserResponse(
        id=user.id,
        email=email,
        display_name=user.display_name,
        roles=roles,
        status=user.status.value,
    )


@auth_router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Revoke session and clear authentication cookie",
)
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
    user: User | None = Depends(get_current_user),
) -> MessageResponse:
    """Revoke session token in Redis and clear the authentication cookie."""
    raw_token = extract_token_from_request(request)
    if raw_token:
        user_id = user.id if user else None
        await logout_user(db, raw_token, user_id)

    clear_session_cookie(response)
    return MessageResponse(message="Successfully logged out")


@auth_router.get(
    "/me",
    response_model=MeResponse,
    summary="Retrieve current authenticated user profile",
)
async def get_me(
    user: User = Depends(require_authenticated_user),
) -> MeResponse:
    """Return identity and session information for the current user."""
    email = user.credential.email if user.credential else ""
    roles = [ur.role.name for ur in user.roles]

    expires_at_str = getattr(user, "_session_expires_at", None)
    expires_at_dt = (
        datetime.fromisoformat(expires_at_str) if isinstance(expires_at_str, str) else None
    )

    return MeResponse(
        id=user.id,
        email=email,
        display_name=user.display_name,
        roles=roles,
        status=user.status.value,
        session_expires_at=expires_at_dt,
    )
