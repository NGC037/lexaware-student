from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import (
    extract_token_from_request,
    get_current_user,
    require_authenticated_user,
    verify_csrf_protection,
)
from app.auth.schemas import (
    CSRFTokenResponse,
    LoginRequest,
    MeResponse,
    MessageResponse,
    RegisterRequest,
    RegisterResponse,
    UserResponse,
)
from app.auth.service import authenticate_user, logout_user, register_user
from app.auth.tokens import generate_csrf_token
from app.core.config import get_settings
from app.db.models import User
from app.db.session import get_db_session

settings = get_settings()

auth_router = APIRouter(prefix="/auth", tags=["authentication"])


def set_auth_cookies(response: Response, raw_token: str, csrf_token: str) -> None:
    """Set the HttpOnly session cookie and the client-readable CSRF cookie."""
    max_age_seconds = settings.access_token_expire_minutes * 60

    # 1. HttpOnly session cookie — inaccessible to client JavaScript
    response.set_cookie(
        key="lexaware_session",
        value=raw_token,
        max_age=max_age_seconds,
        httponly=True,
        secure=settings.is_production,
        samesite="lax",
        path="/",
    )

    # 2. Client-readable CSRF cookie for Double-Submit CSRF pattern
    response.set_cookie(
        key="lexaware_csrf",
        value=csrf_token,
        max_age=max_age_seconds,
        httponly=False,
        secure=settings.is_production,
        samesite="lax",
        path="/",
    )


def clear_auth_cookies(response: Response) -> None:
    """Clear all authentication and CSRF cookies."""
    response.delete_cookie(
        key="lexaware_session",
        path="/",
        httponly=True,
        secure=settings.is_production,
        samesite="lax",
    )
    response.delete_cookie(
        key="lexaware_csrf",
        path="/",
        httponly=False,
        secure=settings.is_production,
        samesite="lax",
    )


@auth_router.get(
    "/csrf",
    response_model=CSRFTokenResponse,
    summary="Retrieve a new CSRF token and set the CSRF cookie",
)
async def get_csrf_token(response: Response) -> CSRFTokenResponse:
    """Generate and deliver a fresh CSRF token for the frontend application."""
    csrf_token = generate_csrf_token()
    response.set_cookie(
        key="lexaware_csrf",
        value=csrf_token,
        max_age=settings.access_token_expire_minutes * 60,
        httponly=False,
        secure=settings.is_production,
        samesite="lax",
        path="/",
    )
    return CSRFTokenResponse(csrf_token=csrf_token)


@auth_router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new student account",
)
async def register(
    req: RegisterRequest,
    db: AsyncSession = Depends(get_db_session),
) -> RegisterResponse:
    """Register a new user account with privacy-preserving uniform acknowledgment."""
    _created, email = await register_user(db, req)
    return RegisterResponse(
        message=(
            "Registration received. If your email is eligible and not already registered, "
            "your account has been created. You may now log in."
        ),
        email=email,
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
    """Authenticate email and password, returning an HttpOnly session cookie and CSRF cookie."""
    client_ip = request.client.host if request.client else "127.0.0.1"

    user, email, roles, raw_token, _expires_at = await authenticate_user(
        db, email=req.email, password=req.password, ip_address=client_ip
    )

    csrf_token = generate_csrf_token()
    set_auth_cookies(response, raw_token=raw_token, csrf_token=csrf_token)

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
    dependencies=[Depends(verify_csrf_protection)],
    summary="Revoke session and clear authentication cookies",
)
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
    user: User | None = Depends(get_current_user),
) -> MessageResponse:
    """Revoke session token in Redis and clear authentication and CSRF cookies."""
    raw_token, _ = extract_token_from_request(request)
    if raw_token:
        user_id = user.id if user else None
        await logout_user(db, raw_token, user_id)

    clear_auth_cookies(response)
    return MessageResponse(message="Successfully logged out")


@auth_router.get(
    "/me",
    response_model=MeResponse,
    summary="Retrieve current authenticated user profile",
)
async def get_me(
    request: Request,
    user: User = Depends(require_authenticated_user),
) -> MeResponse:
    """Return identity and session information for the current user."""
    email = user.credential.email if user.credential else ""
    roles = [ur.role.name for ur in user.roles]
    session_expires_at = getattr(request.state, "session_expires_at", None)

    return MeResponse(
        id=user.id,
        email=email,
        display_name=user.display_name,
        roles=roles,
        status=user.status.value,
        session_expires_at=session_expires_at,
    )
