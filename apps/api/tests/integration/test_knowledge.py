from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import select

from app.db.models import (
    AuditEvent,
    Role,
    User,
    UserCredential,
    UserRole,
)
from app.db.session import AsyncSessionLocal


async def create_test_user_with_role(role_name: str) -> tuple[dict[str, str], User]:
    """Helper to create a user with a specific role and generate a valid session cookie."""
    suffix = uuid4().hex[:8]
    email = f"user_{role_name}_{suffix}@example.com"
    password = "SecurePassword123!"

    async with AsyncSessionLocal() as session:
        # Get or create role
        role_stmt = select(Role).where(Role.name == role_name)
        role = (await session.execute(role_stmt)).scalar_one_or_none()
        if not role:
            role = Role(name=role_name, description=f"{role_name.capitalize()} role")
            session.add(role)
            await session.flush()

        user = User(display_name=f"Test {role_name.capitalize()}")
        session.add(user)
        await session.flush()

        from app.auth.service import hash_password

        cred = UserCredential(
            user_id=user.id,
            email=email,
            password_hash=hash_password(password),
        )
        session.add(cred)
        session.add(UserRole(user_id=user.id, role_id=role.id))
        await session.commit()
        await session.refresh(user)

    from app.auth.tokens import create_session

    token, _ = await create_session(str(user.id))
    return {"lexaware_session": token}, user


@pytest.mark.asyncio
async def test_jurisdiction_and_source_governance(async_client: httpx.AsyncClient) -> None:
    admin_cookies, _ = await create_test_user_with_role("admin")
    student_cookies, _ = await create_test_user_with_role("student")

    # 1. Non-admin cannot create jurisdiction
    jur_payload = {"code": "IN-KA", "name": "Karnataka, India"}
    res_forbidden = await async_client.post(
        "/api/v1/admin/knowledge/jurisdictions",
        json=jur_payload,
        cookies=student_cookies,
    )
    assert res_forbidden.status_code == 403

    # 2. Admin can create jurisdiction
    res_admin = await async_client.post(
        "/api/v1/admin/knowledge/jurisdictions",
        json=jur_payload,
        cookies=admin_cookies,
    )
    assert res_admin.status_code == 201
    jur_data = res_admin.json()
    assert jur_data["code"] == "IN-KA"
    jur_id = jur_data["id"]

    # 3. Public list of jurisdictions accessible without auth
    res_pub_jur = await async_client.get("/api/v1/knowledge/jurisdictions")
    assert res_pub_jur.status_code == 200
    assert any(j["code"] == "IN-KA" for j in res_pub_jur.json())

    # 4. Register authoritative legal source
    source_payload = {
        "jurisdiction_id": jur_id,
        "title": "Karnataka Educational Institutions (Prohibition of Ragging) Act, 1998",
        "publisher": "Government of Karnataka",
        "source_url": "https://dpal.karnataka.gov.in/act_1998",
        "citation": "Karnataka Act No. 2 of 1998",
    }
    res_src = await async_client.post(
        "/api/v1/admin/knowledge/sources",
        json=source_payload,
        cookies=admin_cookies,
    )
    assert res_src.status_code == 201
    src_data = res_src.json()
    assert src_data["title"] == source_payload["title"]
    assert src_data["is_active"] is True


@pytest.mark.asyncio
async def test_complete_knowledge_lifecycle_and_invariants(
    async_client: httpx.AsyncClient,
) -> None:
    admin_cookies, _ = await create_test_user_with_role("admin")
    reviewer_cookies, _ = await create_test_user_with_role("reviewer")
    publisher_cookies, _ = await create_test_user_with_role("publisher")
    student_cookies, _ = await create_test_user_with_role("student")

    # Step 1: Create Jurisdiction & Source
    jur_res = await async_client.post(
        "/api/v1/admin/knowledge/jurisdictions",
        json={"code": "IN-FED", "name": "India Federal / UGC"},
        cookies=admin_cookies,
    )
    jur_id = jur_res.json()["id"]

    src_res = await async_client.post(
        "/api/v1/admin/knowledge/sources",
        json={
            "jurisdiction_id": jur_id,
            "title": "UGC Regulations on Curbing Ragging in Higher Educational Institutions, 2009",
            "publisher": "University Grants Commission",
            "source_url": "https://www.ugc.gov.in/ragging_regulations",
            "citation": "No. F. 1-16/2007 (CPP-II)",
        },
        cookies=admin_cookies,
    )
    src_id = src_res.json()["id"]

    # Step 2: Create Knowledge Item and v1 Draft
    slug = f"ugc-anti-ragging-rights-{uuid4().hex[:6]}"
    item_payload = {
        "jurisdiction_id": jur_id,
        "category": "ragging",
        "topic": "Anti-Ragging Regulations",
        "audience": "undergraduate_students",
        "slug": slug,
        "title": "Understanding Your Rights Against Ragging in College",
        "source_id": src_id,
        "content": (
            "Ragging is strictly prohibited under UGC regulations. "
            "Every student has a legal right to a safe academic environment."
        ),
        "summary": "Plain language guide explaining ragging definitions and immediate protections.",
        "applicability_notes": (
            "Applies to all UGC-recognized universities, colleges, and affiliated institutions."
        ),
        "escalation_guidance": (
            "In case of threat, contact the 24x7 Anti-Ragging Helpline (1800-180-5522) "
            "or campus Squad."
        ),
        "review_due_at": (datetime.now(UTC) + timedelta(days=90)).isoformat(),
    }

    item_res = await async_client.post(
        "/api/v1/admin/knowledge/items",
        json=item_payload,
        cookies=reviewer_cookies,
    )
    assert item_res.status_code == 201
    item_data = item_res.json()
    item_id = item_data["id"]
    assert len(item_data["versions"]) == 1
    v1 = item_data["versions"][0]
    v1_id = v1["id"]
    assert v1["publication_state"] == "draft"
    assert v1["version_number"] == 1

    # Invisibility check: Draft is invisible on public student endpoints
    pub_list_before = await async_client.get("/api/v1/knowledge/articles?category=ragging")
    assert pub_list_before.status_code == 200
    assert not any(a["slug"] == slug for a in pub_list_before.json())

    pub_detail_before = await async_client.get(f"/api/v1/knowledge/articles/{slug}")
    assert pub_detail_before.status_code == 404

    # Step 3: Update draft content
    update_res = await async_client.put(
        f"/api/v1/admin/knowledge/versions/{v1_id}",
        json={
            "content": (
                "Ragging is strictly prohibited under UGC regulations (expanded guidelines). "
                "Every student has an absolute right to physical safety and psychological dignity."
            ),
            "change_summary": "Expanded dignity protections in initial draft.",
        },
        cookies=reviewer_cookies,
    )
    assert update_res.status_code == 200
    assert update_res.json()["change_summary"] == "Expanded dignity protections in initial draft."

    # Step 4: Submit version for review
    submit_res = await async_client.post(
        f"/api/v1/admin/knowledge/versions/{v1_id}/submit-review",
        cookies=reviewer_cookies,
    )
    assert submit_res.status_code == 200
    assert submit_res.json()["publication_state"] == "in_review"

    # Invariant: Directly editing an in-review version is forbidden
    edit_rejected = await async_client.put(
        f"/api/v1/admin/knowledge/versions/{v1_id}",
        json={"content": "Attempting unauthorized modification while in review."},
        cookies=reviewer_cookies,
    )
    assert edit_rejected.status_code == 400
    assert "Only versions in 'draft' state can be edited" in edit_rejected.json()["detail"]

    # Step 5: Reject review -> returns to draft
    reject_res = await async_client.post(
        f"/api/v1/admin/knowledge/versions/{v1_id}/review",
        json={"decision": "reject", "notes": "Please verify penal consequences section."},
        cookies=reviewer_cookies,
    )
    assert reject_res.status_code == 200
    assert reject_res.json()["publication_state"] == "draft"

    # Step 6: Re-submit and Approve review
    await async_client.post(
        f"/api/v1/admin/knowledge/versions/{v1_id}/submit-review",
        cookies=reviewer_cookies,
    )
    approve_res = await async_client.post(
        f"/api/v1/admin/knowledge/versions/{v1_id}/review",
        json={"decision": "approve", "notes": "Statutory citations and helpline numbers verified."},
        cookies=reviewer_cookies,
    )
    assert approve_res.status_code == 200
    assert approve_res.json()["publication_state"] == "approved"
    assert approve_res.json()["reviewed_at"] is not None

    # Step 7: Publishing permissions: Reviewer cannot publish (needs publisher/admin)
    pub_unauth = await async_client.post(
        f"/api/v1/admin/knowledge/versions/{v1_id}/publish",
        cookies=reviewer_cookies,
    )
    assert pub_unauth.status_code == 403

    # Publisher publishes version v1
    pub_res = await async_client.post(
        f"/api/v1/admin/knowledge/versions/{v1_id}/publish",
        cookies=publisher_cookies,
    )
    assert pub_res.status_code == 200
    assert pub_res.json()["publication_state"] == "published"
    assert pub_res.json()["published_at"] is not None

    # Step 8: Verify Student Public Read Boundary (Student can now discover & read v1)
    student_list = await async_client.get("/api/v1/knowledge/articles?category=ragging")
    assert student_list.status_code == 200
    matched_list = [a for a in student_list.json() if a["slug"] == slug]
    assert len(matched_list) == 1
    assert matched_list[0]["category"] == "ragging"
    assert "UGC Regulations" in matched_list[0]["source_title"]

    student_detail = await async_client.get(f"/api/v1/knowledge/articles/{slug}")
    assert student_detail.status_code == 200
    detail_data = student_detail.json()
    assert detail_data["version_number"] == 1
    assert "Anti-Ragging Helpline" in detail_data["escalation_guidance"]
    assert detail_data["source"]["citation"] == "No. F. 1-16/2007 (CPP-II)"

    # Step 9: Version 2 Lifecycle and Automatic Superseding
    # Create v2 draft
    v2_res = await async_client.post(
        f"/api/v1/admin/knowledge/items/{item_id}/versions",
        json={
            "content": (
                "Updated 2026 guidelines on digital harassment in educational context. "
                "Ragging policies apply to cyber spaces as well."
            ),
            "summary": "Updated guide with 2026 digital harassment inclusions.",
            "applicability_notes": "All UGC recognized universities including online portals.",
            "escalation_guidance": "Escalate to cyber cell or campus squad immediately.",
            "change_summary": "Added cyber harassment coverage for v2.",
        },
        cookies=reviewer_cookies,
    )
    assert v2_res.status_code == 201
    v2_data = v2_res.json()
    v2_id = v2_data["id"]
    assert v2_data["version_number"] == 2
    assert v2_data["publication_state"] == "draft"

    # Public endpoint still serves v1
    student_check_v1 = await async_client.get(f"/api/v1/knowledge/articles/{slug}")
    assert student_check_v1.json()["version_number"] == 1

    # Review and approve v2
    await async_client.post(
        f"/api/v1/admin/knowledge/versions/{v2_id}/submit-review",
        cookies=reviewer_cookies,
    )
    await async_client.post(
        f"/api/v1/admin/knowledge/versions/{v2_id}/review",
        json={"decision": "approve", "notes": "Cyber additions verified against IT Act."},
        cookies=reviewer_cookies,
    )

    # Publish v2 -> v1 must automatically transition to SUPERSEDED
    pub_v2_res = await async_client.post(
        f"/api/v1/admin/knowledge/versions/{v2_id}/publish",
        cookies=publisher_cookies,
    )
    assert pub_v2_res.status_code == 200
    assert pub_v2_res.json()["publication_state"] == "published"

    # Verify v1 is now SUPERSEDED in admin view
    item_admin_check = await async_client.get(
        f"/api/v1/admin/knowledge/items/{item_id}",
        cookies=reviewer_cookies,
    )
    versions_map = {v["version_number"]: v for v in item_admin_check.json()["versions"]}
    assert versions_map[1]["publication_state"] == "superseded"
    assert versions_map[2]["publication_state"] == "published"

    # Public endpoint now serves v2 immediately
    student_check_v2 = await async_client.get(f"/api/v1/knowledge/articles/{slug}")
    assert student_check_v2.json()["version_number"] == 2
    assert "digital harassment" in student_check_v2.json()["content"]

    # Step 10: Unpublish / Archive workflow
    unpub_res = await async_client.post(
        f"/api/v1/admin/knowledge/versions/{v2_id}/unpublish?reason=Replaced_by_statutory_repeal",
        cookies=publisher_cookies,
    )
    assert unpub_res.status_code == 200
    assert unpub_res.json()["publication_state"] == "archived"

    # Public endpoint returns 404 once archived
    student_archived_check = await async_client.get(f"/api/v1/knowledge/articles/{slug}")
    assert student_archived_check.status_code == 404

    # Verify audit trail in database
    async with AsyncSessionLocal() as session:
        audits = (
            (
                await session.execute(
                    select(AuditEvent).where(AuditEvent.resource_id.in_([item_id, v1_id, v2_id]))
                )
            )
            .scalars()
            .all()
        )
        actions = [a.action for a in audits]
        assert "knowledge.item.created" in actions
        assert "knowledge.version.created" in actions
        assert "knowledge.version.approved" in actions
        assert "knowledge.version.published" in actions
        assert "knowledge.version.superseded" in actions
        assert "knowledge.version.unpublished" in actions


@pytest.mark.asyncio
async def test_publication_invariants_enforcement(async_client: httpx.AsyncClient) -> None:
    admin_cookies, _ = await create_test_user_with_role("admin")
    publisher_cookies, _ = await create_test_user_with_role("publisher")
    reviewer_cookies, _ = await create_test_user_with_role("reviewer")

    # Create jurisdiction & source
    jur = (
        await async_client.post(
            "/api/v1/admin/knowledge/jurisdictions",
            json={"code": "IN-MH", "name": "Maharashtra"},
            cookies=admin_cookies,
        )
    ).json()

    src = (
        await async_client.post(
            "/api/v1/admin/knowledge/sources",
            json={
                "jurisdiction_id": jur["id"],
                "title": "Maharashtra Tenancy and Agricultural Lands Act",
                "source_url": "https://bombayhighcourt.nic.in/act_tenancy",
            },
            cookies=admin_cookies,
        )
    ).json()

    # Create Item with empty summary and escalation guidance
    item_res = await async_client.post(
        "/api/v1/admin/knowledge/items",
        json={
            "jurisdiction_id": jur["id"],
            "category": "tenancy",
            "slug": f"tenancy-deposit-refund-{uuid4().hex[:6]}",
            "title": "Tenant Security Deposit Recovery in Mumbai",
            "source_id": src["id"],
            "content": "Landlords must refund security deposits upon vacant possession.",
            # Omit summary, applicability_notes, escalation_guidance
        },
        cookies=reviewer_cookies,
    )
    v1_id = item_res.json()["versions"][0]["id"]

    # Try to approve without notes (review works, but publication will fail invariants)
    await async_client.post(
        f"/api/v1/admin/knowledge/versions/{v1_id}/submit-review",
        cookies=reviewer_cookies,
    )
    await async_client.post(
        f"/api/v1/admin/knowledge/versions/{v1_id}/review",
        json={"decision": "approve"},
        cookies=reviewer_cookies,
    )

    # Attempt publication -> Must fail with 400 due to missing mandatory invariants
    pub_fail = await async_client.post(
        f"/api/v1/admin/knowledge/versions/{v1_id}/publish",
        cookies=publisher_cookies,
    )
    assert pub_fail.status_code == 400
    assert "Publication invariants not met" in pub_fail.json()["detail"]
    assert "summary is required" in pub_fail.json()["detail"]


@pytest.mark.asyncio
async def test_stale_review_queue_and_scheduling(async_client: httpx.AsyncClient) -> None:
    admin_cookies, _ = await create_test_user_with_role("admin")
    publisher_cookies, _ = await create_test_user_with_role("publisher")
    reviewer_cookies, _ = await create_test_user_with_role("reviewer")

    jur = (
        await async_client.post(
            "/api/v1/admin/knowledge/jurisdictions",
            json={"code": "IN-TN", "name": "Tamil Nadu"},
            cookies=admin_cookies,
        )
    ).json()

    src = (
        await async_client.post(
            "/api/v1/admin/knowledge/sources",
            json={
                "jurisdiction_id": jur["id"],
                "title": "Tamil Nadu Prohibition of Ragging Act, 1997",
                "source_url": "https://cms.tn.gov.in/sites/default/files/acts/ragging_act.pdf",
            },
            cookies=admin_cookies,
        )
    ).json()

    past_due = datetime.now(UTC) - timedelta(days=5)

    item_res = await async_client.post(
        "/api/v1/admin/knowledge/items",
        json={
            "jurisdiction_id": jur["id"],
            "category": "ragging",
            "slug": f"tn-ragging-law-{uuid4().hex[:6]}",
            "title": "Tamil Nadu Strict Anti-Ragging Provisions",
            "source_id": src["id"],
            "content": (
                "Ragging in Tamil Nadu institutions is strictly prohibited "
                "with mandatory FIR filing requirements."
            ),
            "summary": "Summary of Tamil Nadu anti-ragging law and mandatory police FIR rules.",
            "applicability_notes": "Applies across all educational institutions in Tamil Nadu.",
            "escalation_guidance": "Report to Head of Institution and local police station.",
            "review_due_at": past_due.isoformat(),
        },
        cookies=reviewer_cookies,
    )
    v1_id = item_res.json()["versions"][0]["id"]

    # Submit, approve, and publish
    await async_client.post(
        f"/api/v1/admin/knowledge/versions/{v1_id}/submit-review",
        cookies=reviewer_cookies,
    )
    await async_client.post(
        f"/api/v1/admin/knowledge/versions/{v1_id}/review",
        json={"decision": "approve"},
        cookies=reviewer_cookies,
    )
    await async_client.post(
        f"/api/v1/admin/knowledge/versions/{v1_id}/publish",
        cookies=publisher_cookies,
    )

    # Check stale reviews endpoint (FR-27)
    stale_res = await async_client.get(
        "/api/v1/admin/knowledge/stale-reviews",
        cookies=reviewer_cookies,
    )
    assert stale_res.status_code == 200
    stale_items = stale_res.json()
    assert any(s["id"] == v1_id for s in stale_items)

    # Reschedule review to future
    future_date = datetime.now(UTC) + timedelta(days=180)
    sched_res = await async_client.post(
        f"/api/v1/admin/knowledge/versions/{v1_id}/schedule-review",
        json={"review_due_at": future_date.isoformat()},
        cookies=reviewer_cookies,
    )
    assert sched_res.status_code == 200

    # Verify item is no longer in stale reviews queue
    stale_res_after = await async_client.get(
        "/api/v1/admin/knowledge/stale-reviews",
        cookies=reviewer_cookies,
    )
    assert not any(s["id"] == v1_id for s in stale_res_after.json())


@pytest.mark.asyncio
async def test_search_and_category_discovery(async_client: httpx.AsyncClient) -> None:
    admin_cookies, _ = await create_test_user_with_role("admin")
    publisher_cookies, _ = await create_test_user_with_role("publisher")
    reviewer_cookies, _ = await create_test_user_with_role("reviewer")

    jur = (
        await async_client.post(
            "/api/v1/admin/knowledge/jurisdictions",
            json={"code": "IN-UP", "name": "Uttar Pradesh"},
            cookies=admin_cookies,
        )
    ).json()

    src = (
        await async_client.post(
            "/api/v1/admin/knowledge/sources",
            json={
                "jurisdiction_id": jur["id"],
                "title": "Consumer Protection (E-Commerce) Rules, 2020",
                "source_url": "https://consumeraffairs.nic.in/ecommerce_rules",
            },
            cookies=admin_cookies,
        )
    ).json()

    unique_keyword = f"edtechrefund{uuid4().hex[:4]}"

    item_res = await async_client.post(
        "/api/v1/admin/knowledge/items",
        json={
            "jurisdiction_id": jur["id"],
            "category": "consumer_rights",
            "topic": "EdTech Refunds",
            "slug": f"edtech-refund-rights-{uuid4().hex[:6]}",
            "title": f"Student Course Fee Refund Rights ({unique_keyword})",
            "source_id": src["id"],
            "content": (f"Coaching platforms cannot withhold refunds unfairly ({unique_keyword})."),
            "summary": "Guide on claiming refunds from coaching institutes and unfair contracts.",
            "applicability_notes": "All students enrolled in coaching centers or online courses.",
            "escalation_guidance": "File grievance on National Consumer Helpline (1915).",
        },
        cookies=reviewer_cookies,
    )
    v1_id = item_res.json()["versions"][0]["id"]

    await async_client.post(
        f"/api/v1/admin/knowledge/versions/{v1_id}/submit-review",
        cookies=reviewer_cookies,
    )
    await async_client.post(
        f"/api/v1/admin/knowledge/versions/{v1_id}/review",
        json={"decision": "approve"},
        cookies=reviewer_cookies,
    )
    await async_client.post(
        f"/api/v1/admin/knowledge/versions/{v1_id}/publish",
        cookies=publisher_cookies,
    )

    # 1. Category listing endpoint reflects consumer_rights category count
    cat_res = await async_client.get("/api/v1/knowledge/categories")
    assert cat_res.status_code == 200
    cat_map = {c["category"]: c["article_count"] for c in cat_res.json()}
    assert "consumer_rights" in cat_map
    assert cat_map["consumer_rights"] >= 1

    # 2. Search query matches keyword
    search_res = await async_client.get(f"/api/v1/knowledge/articles?q={unique_keyword}")
    assert search_res.status_code == 200
    assert len(search_res.json()) >= 1
    assert unique_keyword in search_res.json()[0]["title"]
