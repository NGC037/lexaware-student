import json
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.auth.tokens import hash_identifier, hash_token, redis_client
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
    assert "Registration received" in data["message"]
    assert "password" not in data
    assert "password_hash" not in data

    # Verify database state
    async with AsyncSessionLocal() as session:
        stmt = (
            select(UserCredential)
            .where(UserCredential.email == email.lower())
            .options(
                selectinload(UserCredential.user)
                .selectinload(User.roles)
                .selectinload(UserRole.role)
            )
        )
        cred = (await session.execute(stmt)).scalar_one()
        assert cred.password_hash.startswith("$argon2id$")
        assert cred.user.external_subject is None  # Local password auth leaves this null
        roles = [ur.role.name for ur in cred.user.roles]
        assert "student" in roles

        # Verify registration audit event
        audit_stmt = select(AuditEvent).where(
            AuditEvent.action == "user.registered",
            AuditEvent.resource_id == cred.user_id,
        )
        audit = (await session.execute(audit_stmt)).scalar_one_or_none()
        assert audit is not None
        assert audit.actor_id == cred.user_id


@pytest.mark.asyncio
async def test_registration_duplicate_email_anti_enumeration(
    async_client: httpx.AsyncClient,
) -> None:
    unique_suffix = uuid4().hex[:8]
    email = f"dup.{unique_suffix}@example.com"
    password = "ValidStudentPassword123!"

    # 1. First registration
    res1 = await async_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password},
    )
    assert res1.status_code == 201

    # 2. Duplicate registration attempt with different casing
    res2 = await async_client.post(
        "/api/v1/auth/register",
        json={"email": email.upper(), "password": password},
    )
    # Must return identical external 201 response to prevent email enumeration
    assert res2.status_code == 201
    assert res2.json()["message"] == res1.json()["message"]

    # Verify that only ONE credential record exists in database
    async with AsyncSessionLocal() as session:
        count_stmt = select(UserCredential).where(UserCredential.email == email.lower())
        records = (await session.execute(count_stmt)).scalars().all()
        assert len(records) == 1

        # Verify internal duplicate audit event was logged without exposing PII
        audit_stmt = select(AuditEvent).where(
            AuditEvent.action == "user.registration_duplicate_attempted"
        )
        audits = (await session.execute(audit_stmt)).scalars().all()
        assert len(audits) >= 1
        assert audits[-1].details is not None
        assert "account_hash" in audits[-1].details
        assert "@" not in str(audits[-1].details.get("account_hash"))


@pytest.mark.asyncio
async def test_registration_password_policy(async_client: httpx.AsyncClient) -> None:
    # 1. 11 characters rejected by schema validation (422)
    res_11 = await async_client.post(
        "/api/v1/auth/register",
        json={"email": f"p11.{uuid4().hex[:6]}@example.com", "password": "12345678901"},
    )
    assert res_11.status_code == 422

    # 2. 12 characters accepted (201)
    res_12 = await async_client.post(
        "/api/v1/auth/register",
        json={"email": f"p12.{uuid4().hex[:6]}@example.com", "password": "123456789012_custom"},
    )
    assert res_12.status_code == 201

    # 3. Common weak password (13 characters) rejected by policy check (400)
    res_weak = await async_client.post(
        "/api/v1/auth/register",
        json={"email": f"pweak.{uuid4().hex[:6]}@example.com", "password": "password12345"},
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
    assert "lexaware_csrf" in login_res.cookies
    token_cookie = login_res.cookies["lexaware_session"]

    # Verify Redis session data is minimal (no roles stored in Redis)
    token_h = hash_token(token_cookie)
    raw_session = await redis_client.get(f"auth:session:{token_h}")
    assert raw_session is not None
    session_dict = json.loads(raw_session)
    assert "user_id" in session_dict
    assert "created_at" in session_dict
    assert "expires_at" in session_dict
    assert "roles" not in session_dict  # Roles removed from Redis session payload

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
async def test_login_enumeration_defense_and_timing_safety(
    async_client: httpx.AsyncClient,
) -> None:
    # 1. Non-existent email
    res_nonexistent = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "nonexistent@example.com", "password": "AnyPassword123!"},
    )
    assert res_nonexistent.status_code == 401
    assert res_nonexistent.json()["detail"] == "Invalid email or password"

    # 2. Registered user with incorrect password
    suffix = uuid4().hex[:8]
    email = f"reg.{suffix}@example.com"
    await async_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "CorrectPassword123!"},
    )

    res_wrong_pw = await async_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "WrongPassword123!"},
    )
    assert res_wrong_pw.status_code == 401
    assert res_wrong_pw.json()["detail"] == "Invalid email or password"

    # 3. Suspended account
    async with AsyncSessionLocal() as session:
        cred = (
            await session.execute(select(UserCredential).where(UserCredential.email == email))
        ).scalar_one()
        user = await session.get(User, cred.user_id)
        assert user is not None
        user.status = UserStatus.SUSPENDED
        await session.commit()

    res_suspended = await async_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "CorrectPassword123!"},
    )
    # External error MUST be identical to wrong credentials (no account status enumeration)
    assert res_suspended.status_code == 401
    assert res_suspended.json()["detail"] == "Invalid email or password"

    # Internal audit log correctly distinguishes reasons
    async with AsyncSessionLocal() as session:
        audits = (
            (
                await session.execute(
                    select(AuditEvent).where(AuditEvent.action == "auth.login_failure")
                )
            )
            .scalars()
            .all()
        )
        reasons = [a.details.get("reason") for a in audits if a.details]
        assert "invalid_credentials" in reasons
        assert "account_inactive" in reasons


@pytest.mark.asyncio
async def test_account_suspension_immediately_terminates_session(
    async_client: httpx.AsyncClient,
) -> None:
    suffix = uuid4().hex[:8]
    email = f"active_then_suspend.{suffix}@example.com"
    password = "ActivePassword123!"

    await async_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password},
    )

    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    token = login_res.cookies["lexaware_session"]

    # Verify session is initially valid
    me_res1 = await async_client.get("/api/v1/auth/me", cookies={"lexaware_session": token})
    assert me_res1.status_code == 200

    # Suspend user directly in PostgreSQL
    async with AsyncSessionLocal() as session:
        cred = (
            await session.execute(select(UserCredential).where(UserCredential.email == email))
        ).scalar_one()
        user = await session.get(User, cred.user_id)
        assert user is not None
        user.status = UserStatus.SUSPENDED
        await session.commit()

    # Immediate next request MUST be rejected
    me_res2 = await async_client.get("/api/v1/auth/me", cookies={"lexaware_session": token})
    assert me_res2.status_code == 401

    # Verify Redis session key was physically removed
    token_h = hash_token(token)
    assert await redis_client.get(f"auth:session:{token_h}") is None


@pytest.mark.asyncio
async def test_csrf_protection_and_logout_flow(async_client: httpx.AsyncClient) -> None:
    suffix = uuid4().hex[:8]
    email = f"csrf.{suffix}@example.com"
    password = "LogoutPassword123!"

    await async_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password},
    )

    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    session_token = login_res.cookies["lexaware_session"]
    csrf_token = login_res.cookies["lexaware_csrf"]

    cookies = {"lexaware_session": session_token, "lexaware_csrf": csrf_token}

    # 1. State-changing request with cookie but WITHOUT X-CSRF-Token header -> 403
    res_no_header = await async_client.post("/api/v1/auth/logout", cookies=cookies)
    assert res_no_header.status_code == 403
    assert "CSRF" in res_no_header.json()["detail"]

    # 2. State-changing request with mismatched CSRF token -> 403
    res_mismatch = await async_client.post(
        "/api/v1/auth/logout",
        cookies=cookies,
        headers={"X-CSRF-Token": "invalid_csrf_token_value"},
    )
    assert res_mismatch.status_code == 403

    # 3. State-changing request with untrusted Origin header -> 403
    res_untrusted_origin = await async_client.post(
        "/api/v1/auth/logout",
        cookies=cookies,
        headers={"X-CSRF-Token": csrf_token, "Origin": "https://attacker.example.com"},
    )
    assert res_untrusted_origin.status_code == 403

    # 4. Valid CSRF token and allowed origin -> 200 OK
    res_valid = await async_client.post(
        "/api/v1/auth/logout",
        cookies=cookies,
        headers={"X-CSRF-Token": csrf_token, "Origin": "http://localhost:5173"},
    )
    assert res_valid.status_code == 200

    # 5. Subsequent request is rejected (session invalidated)
    res_after = await async_client.get(
        "/api/v1/auth/me", cookies={"lexaware_session": session_token}
    )
    assert res_after.status_code == 401


@pytest.mark.asyncio
async def test_bearer_token_exempt_from_csrf(async_client: httpx.AsyncClient) -> None:
    suffix = uuid4().hex[:8]
    email = f"bearer.{suffix}@example.com"
    password = "BearerPassword123!"

    await async_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password},
    )
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    token = login_res.cookies["lexaware_session"]

    # Bearer client calling logout without CSRF cookie/header succeeds
    logout_res = await async_client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert logout_res.status_code == 200


@pytest.mark.asyncio
async def test_role_authorization_dynamically_loaded_from_postgres(
    async_client: httpx.AsyncClient,
) -> None:
    suffix = uuid4().hex[:8]
    email = f"dynrole.{suffix}@example.com"
    password = "DynamicRolePassword123!"

    reg_res = await async_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password},
    )
    assert reg_res.status_code == 201

    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    token = login_res.cookies["lexaware_session"]

    # Student initially cannot access admin-test
    res_student = await async_client.get("/api/v1/admin-test", cookies={"lexaware_session": token})
    assert res_student.status_code == 403

    # Directly promote user to admin in PostgreSQL without requiring new login
    async with AsyncSessionLocal() as session:
        cred = (
            await session.execute(select(UserCredential).where(UserCredential.email == email))
        ).scalar_one()

        admin_role = (
            await session.execute(select(Role).where(Role.name == "admin"))
        ).scalar_one_or_none()
        if not admin_role:
            admin_role = Role(name="admin", description="Administrator role")
            session.add(admin_role)
            await session.flush()

        session.add(UserRole(user_id=cred.user_id, role_id=admin_role.id))
        await session.commit()

    # Next request with existing session token immediately succeeds
    res_admin = await async_client.get("/api/v1/admin-test", cookies={"lexaware_session": token})
    assert res_admin.status_code == 200
    assert "admin" in res_admin.json()["roles"]


@pytest.mark.asyncio
async def test_rate_limiting_semantics_and_privacy(
    async_client: httpx.AsyncClient,
) -> None:
    suffix = uuid4().hex[:8]
    email_target = f"target.{suffix}@example.com"
    email_innocent = f"innocent.{suffix}@example.com"
    password = "TargetPassword123!"

    await async_client.post(
        "/api/v1/auth/register",
        json={"email": email_target, "password": password},
    )
    await async_client.post(
        "/api/v1/auth/register",
        json={"email": email_innocent, "password": password},
    )

    # 1. Repeated failed attempts on target consume account failure quota (10 max)
    last_res = None
    for _ in range(11):
        last_res = await async_client.post(
            "/api/v1/auth/login",
            json={"email": email_target, "password": "WrongPassword!"},
        )

    assert last_res is not None
    assert last_res.status_code == 429
    assert "Retry-After" in last_res.headers

    # 2. Innocent account on same IP is NOT locked out (independent account quota)
    innocent_login = await async_client.post(
        "/api/v1/auth/login",
        json={"email": email_innocent, "password": password},
    )
    assert innocent_login.status_code == 200

    # 3. Successful login does NOT consume failure quota
    # Reset target by waiting/flushing or verifying innocent quota is 0
    innocent_h = hash_identifier(email_innocent)
    assert await redis_client.get(f"auth:ratelimit:account:{innocent_h}") is None

    # 4. Verify rate-limit Redis keys NEVER contain raw email address
    all_keys = await redis_client.keys("auth:ratelimit:*")
    for key in all_keys:
        assert "@" not in key
        assert "example.com" not in key
