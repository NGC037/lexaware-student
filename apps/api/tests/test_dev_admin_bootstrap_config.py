import pytest

from app.core.config import Settings
from app.dev_admin_bootstrap import _read_credentials, _validate_local_bootstrap


def test_dev_admin_bootstrap_requires_explicit_local_enablement() -> None:
    local_settings = Settings(environment="development", postgres_host="localhost")
    with pytest.raises(ValueError, match="DEV_ADMIN_BOOTSTRAP_ENABLED"):
        _validate_local_bootstrap(local_settings, {})

    _validate_local_bootstrap(
        local_settings,
        {
            "DEV_ADMIN_BOOTSTRAP_ENABLED": "true",
            "DEV_ADMIN_EMAIL": "local-admin@example.test",
            "DEV_ADMIN_DISPLAY_NAME": "Local Demo Admin",
            "DEV_ADMIN_PASSWORD": "LocalBootstrap-Only-TestPassphrase-2026!",
        },
    )


@pytest.mark.parametrize(
    ("settings", "environ", "message"),
    [
        (
            Settings(environment="production", postgres_host="localhost"),
            {"DEV_ADMIN_BOOTSTRAP_ENABLED": "true"},
            "disabled in this environment",
        ),
        (
            Settings(environment="development", postgres_host="db.example.test"),
            {"DEV_ADMIN_BOOTSTRAP_ENABLED": "true"},
            "local PostgreSQL host",
        ),
    ],
)
def test_dev_admin_bootstrap_refuses_unsafe_environment(
    settings: Settings, environ: dict[str, str], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        _validate_local_bootstrap(settings, environ)


def test_dev_admin_bootstrap_requires_credentials_and_existing_password_policy() -> None:
    with pytest.raises(ValueError, match="environment variables are missing"):
        _read_credentials({"DEV_ADMIN_EMAIL": "local-admin@example.test"})

    with pytest.raises(ValueError, match="invalid or the password"):
        _read_credentials(
            {
                "DEV_ADMIN_EMAIL": "local-admin@example.test",
                "DEV_ADMIN_DISPLAY_NAME": "Local Demo Admin",
                "DEV_ADMIN_PASSWORD": "short",
            }
        )
