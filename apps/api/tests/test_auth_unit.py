import pytest

from app.auth.password import (
    PasswordValidationError,
    hash_password,
    validate_password_strength,
    verify_dummy_password,
    verify_password,
)
from app.auth.tokens import generate_csrf_token, hash_identifier, hash_token, verify_csrf_token


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
    # 1. 11 characters rejected
    with pytest.raises(PasswordValidationError, match="at least 12 characters"):
        validate_password_strength("12345678901")

    # 2. 12 characters accepted
    validate_password_strength("123456789012_custom")

    # 3. 128 characters accepted
    validate_password_strength("A" * 128)

    # 4. > 128 characters rejected
    with pytest.raises(PasswordValidationError, match="not exceed 128"):
        validate_password_strength("A" * 129)

    # 5. Common weak passwords rejected
    with pytest.raises(PasswordValidationError, match="too weak"):
        validate_password_strength("password12345")

    # 6. Unicode / whitespace / passphrase-compatible passwords accepted
    validate_password_strength("correct horse battery staple")
    validate_password_strength("न्याय और कानून २०२६ विद्यार्थी")


def test_token_and_identifier_hashing() -> None:
    raw_token = "a" * 64
    hashed = hash_token(raw_token)

    assert hashed != raw_token
    assert len(hashed) == 64  # SHA-256 hex string length

    # Identifier hashing normalizes and generates 64-character SHA-256 digest
    email_h1 = hash_identifier("Student@Example.EDU")
    email_h2 = hash_identifier("student@example.edu")
    assert email_h1 == email_h2
    assert len(email_h1) == 64
    assert "@" not in email_h1


def test_csrf_token_generation_and_verification() -> None:
    token1 = generate_csrf_token()
    token2 = generate_csrf_token()

    assert len(token1) == 64
    assert token1 != token2

    assert verify_csrf_token(token1, token1) is True
    assert verify_csrf_token(token1, token2) is False
    assert verify_csrf_token(None, token1) is False
    assert verify_csrf_token(token1, "") is False
