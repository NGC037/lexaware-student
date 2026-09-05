# ADR 0004: Opaque Session Tokens & Local Password Authentication

## Status

Accepted

## Context

LexAware Student requires a secure, production-grade identity and authentication foundation. The platform provides sensitive legal awareness and guidance to students. A compromised authentication session or an unrevokable token poses a significant privacy risk.

We evaluated two session architectures:
1. **Stateless JWTs**: Tokens signed by a shared secret (`AUTH_SECRET_KEY`) passed in headers.
2. **Server-Side Opaque Tokens**: Cryptographically random session tokens stored in Redis with immediate revocation support.

## Decisions

### 1. Opaque Session Tokens in Redis over Stateless JWTs
We selected **opaque server-side session tokens** backed by Redis rather than stateless JWTs.

**Rationale:**
- **Instant Revocation**: Stateless JWTs cannot be revoked upon logout or account suspension without complex blacklisting. Opaque tokens stored in Redis can be deleted instantly via `DEL auth:session:{token_hash}`.
- **Security for Sensitive Platforms**: Students querying legal rights or submitting grievances require privacy guarantees. Stolen session credentials must be revokable immediately by the system or user.
- **Minimal Surface Area**: Redis is already deployed in our local and production infrastructure.

### 2. Token Security & Hashing
- **Raw Token**: 32-byte cryptographically secure random token generated via `secrets.token_hex(32)`.
- **Token Hashing**: Raw tokens are **never** stored in Redis. Only the SHA-256 hash `SHA-256(raw_token)` is used as the Redis key: `auth:session:{token_hash}`.
- **Session Payload**: Stores minimal metadata (`user_id`, `roles`, `created_at`, `expires_at`). Internal Redis keys and token hashes are never exposed through API responses or log outputs.
- **Secret Key Handling**: `AUTH_SECRET_KEY` is retained in configuration for future HMAC/webhook signing operations, but is intentionally not used for opaque token generation (which derives security from cryptographic randomness).

### 3. Password Hashing with Argon2id
- User passwords are hashed using **Argon2id** (`argon2-cffi`), the Password Hashing Competition (PHC) winner and OWASP-recommended default.
- Plaintext passwords are never stored, logged, or returned in API responses.
- To prevent timing-based account enumeration, login requests for non-existent accounts trigger a pre-computed dummy Argon2id verification (`verify_dummy_password`).

### 4. Credential Storage & Identity Separation (`User.external_subject`)
- Local password credentials are stored in a dedicated `user_credentials` table (1-to-1 relationship with `users`).
- The `User.external_subject` column is reserved for external identity providers (OAuth/SSO). For local password authentication, `external_subject` remains `NULL`. This keeps the identity model clean for future institutional SSO integration.

### 5. Cookie Security, CORS, and CSRF Protection
- **HttpOnly Cookie**: Session tokens are delivered via an `HttpOnly` cookie named `lexaware_session` to prevent access by client-side JavaScript (XSS mitigation).
- **Secure Flag**: Enabled automatically in production environments (`settings.is_production`).
- **SameSite=Lax**: Restricts cross-site cookie transmission to mitigate CSRF attacks.
- **CORS Protection**: `CORSMiddleware` restricts allowed origins strictly to `settings.web_app_url`. Wildcard origins (`*`) are disallowed when `allow_credentials=True`.

### 6. Layered Rate Limiting
- Rate limits are enforced using Redis counters with a 15-minute sliding window (`auth:ratelimit:ip:{ip}` and `auth:ratelimit:email:{email}`).
- Limits are set intentionally to accommodate shared college networks (hostels, campus Wi-Fi) while preventing brute-force attacks.

## Consequences

- All active sessions are fully stateful and revokable via Redis.
- Logouts completely invalidate sessions across both client cookie state and backend cache.
- The `users` table remains uncoupled from local authentication credentials.
- Future OAuth/SSO can populate `external_subject` without database migrations.
