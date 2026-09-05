# ADR 0004: Opaque Session Tokens, Anti-Enumeration & Authentication Hardening

## Status

Accepted (Hardened)

## Context

LexAware Student provides college students in India with grounded legal awareness, document review assistance, and guided next-step support. A security or privacy compromise—such as session hijacking, credential stuffing, CSRF, or account enumeration—directly undermines the platform's core safety and privacy-by-design promises.

We evaluated session and credential architectures against OWASP ASVS and NIST SP 800-63B standards to establish an industrial-grade identity foundation.

## Decisions

### 1. Opaque Server-Side Session Tokens over Stateless JWTs
We selected **opaque server-side session tokens** backed by Redis rather than stateless JWTs.

**Rationale:**
- **Instant Revocation**: Stateless JWTs cannot be revoked immediately upon logout, credential change, or account suspension without complex distributed blacklists. Opaque tokens stored in Redis are invalidated in O(1) time via `DEL auth:session:{token_hash}`.
- **Immediate Authorization Updates**: Roles are **not** persisted inside the Redis session payload. User roles and account status are resolved directly from PostgreSQL on every request. Any administrative privilege revocation or account suspension takes effect instantly without awaiting session expiration.
- **Minimal Session Footprint**: The Redis session payload stores strictly:
  - `user_id`: UUID of the authenticated user
  - `created_at`: ISO timestamp of session creation
  - `expires_at`: ISO timestamp of expiration
- **ORM Model Cleanliness**: Raw session tokens are never attached to the SQLAlchemy `User` ORM entity or persisted in database records. Active session metadata is carried solely in transient request context (`request.state`).

### 2. Token Security & Cryptographic Hashing
- **Raw Token Generation**: 32-byte cryptographically secure random token generated via `secrets.token_hex(32)`.
- **Token Hashing**: Raw tokens are **never** stored in Redis. Only the SHA-256 digest `SHA-256(raw_token)` serves as the Redis lookup key: `auth:session:{token_hash}`.
- **Secret Key Handling**: `AUTH_SECRET_KEY` is retained in configuration for future cryptographic operations (such as webhook verification or signed links), but is deliberately not used for opaque token generation.

### 3. Password Policy & Argon2id Hashing
- **Argon2id**: Password hashing utilizes `argon2-cffi` configured with PHC and OWASP recommended parameters.
- **NIST SP 800-63B Compliant Policy**:
  - Minimum length: **12 characters** (enforced in both Pydantic schemas and service validation).
  - Maximum length: **128 characters**.
  - Rejection of common, leaked, and easily guessed passwords.
  - **No arbitrary composition rules**: mandatory upper/lower/number/symbol combinations are omitted to encourage memorable passphrases with spaces and unicode.
- **Constant-Time Timing Equalization**: For non-existent accounts, a pre-computed dummy Argon2id hash is verified (`verify_dummy_password`) to equalize execution time and eliminate timing side-channel account enumeration.

### 4. Anti-Enumeration Protections
- **Login Uniformity**: Login attempts for non-existent emails, incorrect passwords, and inactive/suspended accounts return the exact same generic HTTP 401 response: `{"detail": "Invalid email or password"}`. Internal audit events record distinct reasons (`invalid_credentials` vs `account_inactive`) without leaking to client responses.
- **Registration Anti-Enumeration**: Duplicate registration attempts for existing emails do not return an error. The endpoint returns a uniform HTTP 201 response:
  `{"message": "Registration received. If your email is eligible and not already registered, your account has been created. You may now log in.", "email": normalized_email}`
  An internal audit event (`user.registration_duplicate_attempted`) is logged with a privacy-preserving hash.

### 5. Failure-Only Layered Rate Limiting & Privacy
- **Failure-Only Consumption**: The authentication failure quota is consumed **only** upon failed credential verification. Successful logins do not consume failure quota and actively reset any previous failure counters for that account.
- **PII Protection in Redis Keys**: Account rate-limit keys do not contain plaintext email addresses. Keys use SHA-256 hashes:
  - Account key: `auth:ratelimit:account:{sha256(normalized_email)}`
  - Source IP key: `auth:ratelimit:ip:{ip_address}`
- **Campus Network Protection**: Layered quotas prevent shared college hostel/NAT IPs from locking out unaffected student accounts when one student repeatedly misenters credentials.
- **Retry-After Header**: HTTP 429 responses include standard `Retry-After` seconds indicating the remaining lockout window.

### 6. Robust CSRF Architecture for Cookie Authentication
- **HttpOnly Session Cookie**: `lexaware_session` is delivered with `HttpOnly`, `SameSite=Lax`, `Secure` (in production), and `Path=/`.
- **Double-Submit CSRF Protection**:
  - State-changing cookie requests (`POST`, `PUT`, `PATCH`, `DELETE`) require a matching `lexaware_csrf` cookie and `X-CSRF-Token` header.
  - CSRF verification uses constant-time comparison (`secrets.compare_digest`).
  - Origin / Referer validation strictly checks against `settings.web_app_url`.
- **Bearer Token Exemption**: API clients authenticating with `Authorization: Bearer <token>` are exempt from CSRF checks because Authorization headers are not automatically attached by browsers.

### 7. Database Index Cleanliness & Identity Separation
- Removed redundant ordinary index `ix_user_credentials_email` via migration `8cba291f6859`, preserving the native PostgreSQL unique constraint on `email`.
- `User.external_subject` remains `NULL` for local password authentication, keeping the model clean for future institutional SSO / OAuth 2.0 integration.

## Consequences

- Sessions are immediately revokable across both Redis and client cookies.
- Suspended or deleted accounts cannot access endpoints even if an active session exists.
- Role changes made by administrators in PostgreSQL take effect immediately.
- Attackers cannot enumerate student emails via login timing, login responses, or registration responses.
- Shared-IP campus environments are protected from denial-of-service lockouts.
- State-changing browser operations are protected against CSRF without breaking Bearer-token API clients.
