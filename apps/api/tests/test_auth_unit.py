import pytest

from app.auth.password import (
    PasswordValidationError,
    hash_password,
    validate_password_strength,
    verify_dummy_password,
    verify_password,
)
from app.auth.tokens import hash_token


def test_password_hashing_and_verification() -> None:
    plain = "SuperSecurePassword123!"
    hashed = hash_password(plain)

    # Password must never be stored in plaintext
    assert hashed != plain
    assert "$argon2id$" in hashed

    # Verification must succeed for correct password and fail for wrong password
    assert verify_password(plain, hashed) is True
    assert verify_password("WrongPassword123!", hashed) is False


def test_dummy_password_verification() -> None:
    # Dummy verification should always return False safely
    assert verify_dummy_password("AnyPasswordAttempt123!") is False


def test_password_strength_validation() -> None:
    # Valid password
    validate_password_strength("StrongP@ssw0rd2026")

    # Reject short passwords (< 8 chars)
    with pytest.raises(PasswordValidationError, match="at least 8 characters"):
        validate_password_strength("short")

    # Reject weak/common passwords
    with pytest.raises(PasswordValidationError, match="too weak"):
        validate_password_strength("password123")


def test_token_hashing() -> None:
    raw_token = "a" * 64
    hashed = hash_token(raw_token)

    assert hashed != raw_token
    assert len(hashed) == 64  # SHA-256 hex string length
