from uuid import uuid4

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.models import AuditEvent, Role, User, UserCredential, UserRole, UserStatus
from app.db.session import AsyncSessionLocal


@pytest.mark.asyncio
async def test_registration_flow_success(async_client: httpx.AsyncClient) -> None:
    unique_suffix = uuid4().hex[:8]
    email = f"Student.{unique_suffix}@Example.EDU"
    password = "ValidStudentPassword123!"

    response = await async_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "display_name": "Test Student"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["email"] == email.lower()  # Email normalized
    assert data["display_name"] == "Test Student"
    assert "student" in data["roles"]
    assert data["status"] == "active"
    assert "password" not in data
    assert "password_hash" not in data

    # Verify database state
    async with AsyncSessionLocal() as session:
        stmt = (
            select(UserCredential)
            .where(UserCredential.email == email.lower())
            .options(selectinload(UserCredential.user))
        )
        cred = (await session.execute(stmt)).scalar_one()
        assert cred.password_hash.startswith("$argon2id$")
        assert cred.user.external_subject is None  # Local password auth leaves this null

        # Verify registration audit event
        audit_stmt = select(AuditEvent).where(
            AuditEvent.action == "user.registered",
            AuditEvent.resource_id == cred.user_id,
        )
        audit = (await session.execute(audit_stmt)).scalar_one_or_none()
        assert audit is not None
        assert audit.actor_id == cred.user_id


@pytest.mark.asyncio
async def test_registration_duplicate_email_rejected(async_client: httpx.AsyncClient) -> None:
    unique_suffix = uuid4().hex[:8]
    email = f"dup.{unique_suffix}@example.com"
    password = "ValidStudentPassword123!"

    res1 = await async_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password},
    )
    assert res1.status_code == 201

    # Second attempt with same email (different case)
    res2 = await async_client.post(
        "/api/v1/auth/register",
        json={"email": email.upper(), "password": password},
    )
    assert res2.status_code == 400
    assert "already exists" in res2.json()["detail"]


@pytest.mark.asyncio
async def test_registration_weak_password_rejected(async_client: httpx.AsyncClient) -> None:
    # 1. Short password (< 8 chars) fails Pydantic schema validation with 422
    res_short = await async_client.post(
        "/api/v1/auth/register",
        json={"email": f"short.{uuid4().hex[:6]}@example.com", "password": "short"},
    )
    assert res_short.status_code == 422

    # 2. Common weak password ("password123", 11 chars) fails policy check with 400
    res_weak = await async_client.post(
        "/api/v1/auth/register",
        json={"email": f"weak.{uuid4().hex[:6]}@example.com", "password": "password123"},
    )
    assert res_weak.status_code == 400
    assert "too weak" in res_weak.json()["detail"]


@pytest.mark.asyncio
async def test_login_and_me_flow(async_client: httpx.AsyncClient) -> None:
    unique_suffix = uuid4().hex[:8]
    email = f"user.{unique_suffix}@example.com"
    password = "StrongUserPassword123!"

    # 1. Register
    await async_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "display_name": "Login User"},
    )

    # 2. Login
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login_res.status_code == 200
    assert "lexaware_session" in login_res.cookies
    token_cookie = login_res.cookies["lexaware_session"]

    # 3. Access /me with cookie
    me_res = await async_client.get("/api/v1/auth/me", cookies={"lexaware_session": token_cookie})
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["email"] == email
    assert me_data["display_name"] == "Login User"
    assert "student" in me_data["roles"]
    assert "session_expires_at" in me_data

    # 4. Access /me with Bearer header
    me_bearer_res = await async_client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token_cookie}"}
    )
    assert me_bearer_res.status_code == 200
    assert me_bearer_res.json()["email"] == email


@pytest.mark.asyncio
async def test_login_invalid_credentials_returns_generic_error(
    async_client: httpx.AsyncClient,
) -> None:
    # Non-existent user
    res1 = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "nonexistent@example.com", "password": "AnyPassword123!"},
    )
    assert res1.status_code == 401
    assert res1.json()["detail"] == "Invalid email or password"

    # Registered user with wrong password
    suffix = uuid4().hex[:8]
    email = f"reg.{suffix}@example.com"
    await async_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "CorrectPassword123!"},
    )

    res2 = await async_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "WrongPassword123!"},
    )
    assert res2.status_code == 401
    assert res2.json()["detail"] == "Invalid email or password"


@pytest.mark.asyncio
async def test_login_inactive_user_rejected(async_client: httpx.AsyncClient) -> None:
    suffix = uuid4().hex[:8]
    email = f"inactive.{suffix}@example.com"
    password = "ValidPassword123!"

    # Register user
    reg_res = await async_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password},
    )
    user_id = reg_res.json()["id"]

    # Suspend user in DB
    async with AsyncSessionLocal() as session:
        user = await session.get(User, user_id)
        assert user is not None
        user.status = UserStatus.SUSPENDED
        await session.commit()

    # Attempt login
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login_res.status_code == 401
    assert "inactive or suspended" in login_res.json()["detail"]


@pytest.mark.asyncio
async def test_logout_invalidates_session(async_client: httpx.AsyncClient) -> None:
    suffix = uuid4().hex[:8]
    email = f"logout.{suffix}@example.com"
    password = "LogoutPassword123!"

    await async_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password},
    )

    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    token = login_res.cookies["lexaware_session"]

    # Verify authenticated
    me_res1 = await async_client.get("/api/v1/auth/me", cookies={"lexaware_session": token})
    assert me_res1.status_code == 200

    # Logout
    logout_res = await async_client.post("/api/v1/auth/logout", cookies={"lexaware_session": token})
    assert logout_res.status_code == 200

    # Verify session is invalidated
    me_res2 = await async_client.get("/api/v1/auth/me", cookies={"lexaware_session": token})
    assert me_res2.status_code == 401


@pytest.mark.asyncio
async def test_role_based_authorization(async_client: httpx.AsyncClient) -> None:
    suffix = uuid4().hex[:8]

    # 1. Register regular student
    student_email = f"student.{suffix}@example.com"
    await async_client.post(
        "/api/v1/auth/register",
        json={"email": student_email, "password": "StudentPassword123!"},
    )
    login_student = await async_client.post(
        "/api/v1/auth/login",
        json={"email": student_email, "password": "StudentPassword123!"},
    )
    student_token = login_student.cookies["lexaware_session"]

    # Student attempting admin-only endpoint -> 403 Forbidden
    admin_test_res1 = await async_client.get(
        "/api/v1/admin-test", cookies={"lexaware_session": student_token}
    )
    assert admin_test_res1.status_code == 403

    # 2. Register admin user & assign 'admin' role in DB
    admin_email = f"admin.{suffix}@example.com"
    reg_admin = await async_client.post(
        "/api/v1/auth/register",
        json={"email": admin_email, "password": "AdminPassword123!"},
    )
    admin_user_id = reg_admin.json()["id"]

    async with AsyncSessionLocal() as session:
        admin_role_stmt = select(Role).where(Role.name == "admin")
        admin_role = (await session.execute(admin_role_stmt)).scalar_one_or_none()
        if not admin_role:
            admin_role = Role(name="admin", description="Administrator role")
            session.add(admin_role)
            await session.flush()

        session.add(UserRole(user_id=admin_user_id, role_id=admin_role.id))
        await session.commit()

    login_admin = await async_client.post(
        "/api/v1/auth/login",
        json={"email": admin_email, "password": "AdminPassword123!"},
    )
    admin_token = login_admin.cookies["lexaware_session"]

    # Admin accessing admin-only endpoint -> 200 OK
    admin_test_res2 = await async_client.get(
        "/api/v1/admin-test", cookies={"lexaware_session": admin_token}
    )
    assert admin_test_res2.status_code == 200
    assert "admin" in admin_test_res2.json()["roles"]


@pytest.mark.asyncio
async def test_unauthenticated_request_rejected(async_client: httpx.AsyncClient) -> None:
    res = await async_client.get("/api/v1/auth/me")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_authentication_rate_limiting(async_client: httpx.AsyncClient) -> None:
    suffix = uuid4().hex[:8]
    email = f"ratelimit.{suffix}@example.com"
    await async_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "CorrectPassword123!"},
    )

    # Trigger rate limit by sending max_email_attempts (10) failed login attempts
    failed_count = 0
    for _ in range(11):
        res = await async_client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "WrongPassword!"},
        )
        if res.status_code == 429:
            failed_count += 1

    assert failed_count > 0, "Rate limiter did not return HTTP 429 after threshold exceeded"
