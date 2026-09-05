from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

# Initialize Argon2id password hasher with secure defaults
ph = PasswordHasher()

# Pre-computed dummy hash using the same Argon2id hasher to maintain constant-time
# execution during login attempts for non-existent users (prevents timing side-channel
# account enumeration).
DUMMY_PASSWORD_HASH = ph.hash("LexAwareDummyPasswordForConstantTimeVerification123!")


class PasswordValidationError(ValueError):
    """Raised when a password fails policy validation."""

    pass


COMMON_WEAK_PASSWORDS = {
    "password",
    "password123",
    "12345678",
    "123456789",
    "1234567890",
    "qwertyuiop",
    "lexaware123",
    "admin123",
    "student123",
}


def hash_password(password: str) -> str:
    """Hash a plaintext password using Argon2id."""
    return ph.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    """Verify a plaintext password against an Argon2id hash in constant time."""
    try:
        return ph.verify(hashed, password)
    except VerifyMismatchError, VerificationError, InvalidHashError:
        return False


def verify_dummy_password(password: str) -> bool:
    """Perform a dummy verification to equalize timing when an account is not found."""
    verify_password(password, DUMMY_PASSWORD_HASH)
    return False


def validate_password_strength(password: str) -> None:
    """Validate password strength according to student usability guidelines.

    Requirements:
    - Minimum length of 8 characters.
    - Rejection of common/obviously weak passwords.
    """
    if len(password) < 8:
        raise PasswordValidationError("Password must be at least 8 characters long.")

    if len(password) > 128:
        raise PasswordValidationError("Password must not exceed 128 characters.")

    if password.lower() in COMMON_WEAK_PASSWORDS:
        raise PasswordValidationError("Password is too weak or commonly used.")
