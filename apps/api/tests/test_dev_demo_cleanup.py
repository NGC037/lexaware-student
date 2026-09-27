from datetime import UTC, datetime

import pytest

from app.core.config import Settings
from app.db.models import ComplaintGuideVersion, HelpResource, Jurisdiction, Source
from app.dev_demo_cleanup import (
    _complaint_fixture_reason,
    _complaint_guide_fixture_reason,
    _help_fixture_reason,
    validate_cleanup_environment,
)


def test_cleanup_requires_explicit_local_enablement_apply_confirmation_and_actor() -> None:
    local = Settings(environment="development", postgres_host="localhost")
    with pytest.raises(ValueError, match="DEV_DEMO_CLEANUP_ENABLED"):
        validate_cleanup_environment(local, {}, apply=False)

    enabled = {"DEV_DEMO_CLEANUP_ENABLED": "true"}
    validate_cleanup_environment(local, enabled, apply=False)
    with pytest.raises(ValueError, match="--apply requires DEV_DEMO_CLEANUP_CONFIRM"):
        validate_cleanup_environment(local, enabled, apply=True)

    confirmed = enabled | {
        "DEV_DEMO_CLEANUP_CONFIRM": "ARCHIVE_IDENTIFIED_FIXTURES",
    }
    with pytest.raises(ValueError, match="DEV_DEMO_CLEANUP_ACTOR_EMAIL"):
        validate_cleanup_environment(local, confirmed, apply=True)
    validate_cleanup_environment(
        local,
        confirmed | {"DEV_DEMO_CLEANUP_ACTOR_EMAIL": "admin@example.test"},
        apply=True,
    )


@pytest.mark.parametrize(
    ("settings", "environ", "message"),
    [
        (
            Settings(environment="production", postgres_host="localhost"),
            {"DEV_DEMO_CLEANUP_ENABLED": "true"},
            "disabled in this environment",
        ),
        (
            Settings(environment="development", postgres_host="db.example.test"),
            {"DEV_DEMO_CLEANUP_ENABLED": "true"},
            "loopback PostgreSQL host",
        ),
        (
            Settings(environment="test", postgres_host="localhost"),
            {"DEV_DEMO_CLEANUP_ENABLED": "true"},
            "disabled in this environment",
        ),
    ],
)
def test_cleanup_refuses_production_and_non_local_database(
    settings: Settings, environ: dict[str, str], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        validate_cleanup_environment(settings, environ, apply=False)


def test_complaint_candidate_requires_the_complete_fixture_signature() -> None:
    steps = [
        {"instruction": f"Guidance for {section}."}
        for section in (
            "immediate_safety",
            "safety_considerations",
            "preserve_evidence",
            "reporting_options",
            "information_to_prepare",
        )
    ]
    assert _complaint_fixture_reason("Getting help safely", "Test jurisdiction", steps)
    assert (
        _complaint_fixture_reason("Different legitimate title", "Test jurisdiction", steps) is None
    )
    assert _complaint_fixture_reason("Getting help safely", "Delhi", steps) is None
    assert (
        _complaint_fixture_reason(
            "Getting help safely", "Test jurisdiction", steps[:-1] + [{"instruction": "Reviewed"}]
        )
        is None
    )


def test_mixed_complaint_guide_versions_are_not_fixture_candidates() -> None:
    jurisdiction = Jurisdiction(code="T-FIXTURE", name="Test jurisdiction")
    fixture_steps = [
        {"instruction": f"Guidance for {section}."}
        for section in ("safety", "evidence", "reporting", "prepare", "checklist")
    ]
    fixture = ComplaintGuideVersion(title="Getting help safely", guidance_steps=fixture_steps)
    legitimate = ComplaintGuideVersion(
        title="Reviewed safety guidance", guidance_steps=fixture_steps
    )

    assert _complaint_guide_fixture_reason([(fixture, jurisdiction)])
    assert (
        _complaint_guide_fixture_reason([(fixture, jurisdiction), (legitimate, jurisdiction)])
        is None
    )


def test_help_candidate_requires_fixture_source_jurisdiction_and_resource_markers() -> None:
    jurisdiction = Jurisdiction(code="T-FIXTURE", name="Test jurisdiction")
    source = Source(
        jurisdiction_id=jurisdiction.id,
        title="Test official guidance",
        publisher="Public authority",
        source_url="https://example.gov/guidance",
        citation="Guidance 1",
        retrieved_at=datetime.now(UTC),
    )
    resource = HelpResource(
        jurisdiction_id=jurisdiction.id,
        source_id=source.id,
        name="Current student legal aid",
        category="legal_aid",
        resource_type="service",
        assistance_type="legal_advice",
        contact_method="phone",
        phone="18001234567",
    )
    assert _help_fixture_reason(resource, jurisdiction, source)

    legitimate_source = Source(
        jurisdiction_id=jurisdiction.id,
        title="Official support information",
        publisher="Public authority",
        source_url="https://government.example.in/help",
        citation="Public service directory",
        retrieved_at=datetime.now(UTC),
    )
    assert _help_fixture_reason(resource, jurisdiction, legitimate_source) is None

    mismatched_phone = HelpResource(
        jurisdiction_id=jurisdiction.id,
        source_id=source.id,
        name="Current student legal aid",
        category="legal_aid",
        resource_type="service",
        assistance_type="legal_advice",
        contact_method="phone",
        phone="1800114000",
    )
    assert _help_fixture_reason(mismatched_phone, jurisdiction, source) is None
