import uuid
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.password import (
    PasswordValidationError,
    hash_password,
    validate_password_strength,
    verify_dummy_password,
    verify_password,
)
from app.auth.schemas import RegisterRequest
from app.auth.tokens import check_rate_limit, create_session, revoke_session
from app.db.models import AuditEvent, Role, User, UserCredential, UserRole, UserStatus


async def record_audit_event(
    db: AsyncSession,
    action: str,
    resource_type: str = "user",
    resource_id: uuid.UUID | None = None,
    actor_id: uuid.UUID | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """Record a security or authentication audit event."""
    event = AuditEvent(
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        actor_id=actor_id,
        details=details,
    )
    db.add(event)
    await db.flush()


async def register_user(db: AsyncSession, req: RegisterRequest) -> tuple[User, str, list[str]]:
    """Register a new user with local password credentials."""
    normalized_email = req.email.strip().lower()

    # 1. Validate password strength
    try:
        validate_password_strength(req.password)
    except PasswordValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e

    # 2. Check for duplicate email
    existing_stmt = select(UserCredential).where(UserCredential.email == normalized_email)
    existing_res = await db.execute(existing_stmt)
    if existing_res.scalar_one_or_none():
        # Prevent duplicate registration without giving away existing user info
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email address already exists.",
        )

    # 3. Hash password
    pwd_hash = hash_password(req.password)

    # 4. Create User and UserCredential
    user = User(
        display_name=req.display_name,
        status=UserStatus.ACTIVE,
        external_subject=None,  # Reserved for OAuth/SSO; see ADR 0004
    )
    db.add(user)
    await db.flush()

    credential = UserCredential(
        user_id=user.id,
        email=normalized_email,
        password_hash=pwd_hash,
    )
    db.add(credential)

    # 5. Assign default 'student' role
    role_stmt = select(Role).where(Role.name == "student")
    role_res = await db.execute(role_stmt)
    role = role_res.scalar_one_or_none()

    if not role:
        role = Role(name="student", description="Default student role")
        db.add(role)
        await db.flush()

    user_role = UserRole(user_id=user.id, role_id=role.id)
    db.add(user_role)

    # 6. Audit event
    await record_audit_event(
        db,
        action="user.registered",
        resource_id=user.id,
        actor_id=user.id,
    )

    await db.commit()

    # Re-fetch user with relationships loaded
    user_stmt = (
        select(User)
        .where(User.id == user.id)
        .options(selectinload(User.roles).selectinload(UserRole.role))
    )
    user_res = await db.execute(user_stmt)
    full_user = user_res.scalar_one()

    roles = [ur.role.name for ur in full_user.roles]
    return full_user, normalized_email, roles


async def authenticate_user(
    db: AsyncSession, email: str, password: str, ip_address: str
) -> tuple[User, str, list[str], str, Any]:
    """Authenticate user credentials and return a new opaque session token."""
    normalized_email = email.strip().lower()

    # 1. Rate limiting check
    allowed = await check_rate_limit(ip_address=ip_address, normalized_email=normalized_email)
    if not allowed:
        await record_audit_event(
            db,
            action="auth.rate_limited",
            details={"ip": ip_address},
        )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed authentication attempts. Please try again later.",
        )

    # 2. Query user credential with user and roles
    stmt = (
        select(UserCredential)
        .where(UserCredential.email == normalized_email)
        .options(
            selectinload(UserCredential.user).selectinload(User.roles).selectinload(UserRole.role)
        )
    )
    result = await db.execute(stmt)
    credential = result.scalar_one_or_none()

    if not credential:
        # Dummy verification to equalize timing and prevent account enumeration
        verify_dummy_password(password)
        await record_audit_event(
            db,
            action="auth.login_failure",
            details={"reason": "invalid_credentials"},
        )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # 3. Verify password hash
    if not verify_password(password, credential.password_hash):
        await record_audit_event(
            db,
            action="auth.login_failure",
            actor_id=credential.user_id,
            details={"reason": "invalid_credentials"},
        )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    user = credential.user

    # 4. Check user status
    if user.status != UserStatus.ACTIVE:
        await record_audit_event(
            db,
            action="auth.login_failure",
            actor_id=user.id,
            details={"reason": "account_inactive"},
        )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is inactive or suspended",
        )

    # 5. Extract roles and create session
    roles = [ur.role.name for ur in user.roles]
    raw_token, expires_at = await create_session(user.id, roles)

    # 6. Record audit event
    await record_audit_event(
        db,
        action="auth.login_success",
        actor_id=user.id,
        details={"ip": ip_address},
    )
    await db.commit()

    return user, credential.email, roles, raw_token, expires_at


async def logout_user(db: AsyncSession, raw_token: str, user_id: uuid.UUID | None = None) -> None:
    """Revoke session and record logout audit event."""
    await revoke_session(raw_token)
    if user_id:
        await record_audit_event(
            db,
            action="auth.logout",
            actor_id=user_id,
        )
        await db.commit()
