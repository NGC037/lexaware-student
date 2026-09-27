from uuid import uuid4

import httpx
import pytest
from sqlalchemy import func, select

from app.auth.password import hash_password, verify_password
from app.auth.tokens import create_session
from app.db.models import AuditEvent, Role, User, UserCredential, UserRole
from app.db.session import AsyncSessionLocal
from app.dev_admin_bootstrap import _create_admin, _find_credential


@pytest.mark.asyncio
async def test_bootstrap_creates_one_hashed_admin_auditably_and_refuses_promotion(
    async_client: httpx.AsyncClient,
) -> None:
    suffix = uuid4().hex
    email = f"bootstrap-{suffix}@example.test"
    password = "LocalBootstrap-Only-TestPassphrase-2026!"
    async with AsyncSessionLocal() as session:
        assert await _create_admin(session, email, "Local Demo Admin", password)
        assert not await _create_admin(session, email, "Local Demo Admin", password)

        credential = await _find_credential(session, email)
        assert credential is not None
        assert credential.password_hash != password
        assert verify_password(password, credential.password_hash)
        assert any(user_role.role.name == "admin" for user_role in credential.user.roles)
        audit_count = await session.scalar(
            select(func.count(AuditEvent.id)).where(
                AuditEvent.action == "auth.dev_admin_bootstrapped",
                AuditEvent.resource_id == credential.user_id,
            )
        )
        assert audit_count == 1
        admin_id = credential.user_id

        student_role = await session.scalar(select(Role).where(Role.name == "student"))
        if student_role is None:
            student_role = Role(name="student", description="Student role")
            session.add(student_role)
            await session.flush()
        student = User(display_name="Existing Student")
        session.add(student)
        await session.flush()
        session.add(
            UserCredential(
                user_id=student.id,
                email=f"existing-{suffix}@example.test",
                password_hash=hash_password(password),
            )
        )
        session.add(UserRole(user_id=student.id, role_id=student_role.id))
        await session.commit()

        with pytest.raises(ValueError, match="already assigned to a non-admin"):
            await _create_admin(
                session,
                f"existing-{suffix}@example.test",
                "Existing Student",
                password,
            )

    session_token, _expires_at = await create_session(admin_id)
    response = await async_client.get(
        "/api/v1/admin/operations", cookies={"lexaware_session": session_token}
    )
    assert response.status_code == 200
