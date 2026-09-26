# Frontend foundation architecture

The web app is a React 19, TypeScript, and Vite single-page application. It includes the public landing page, registration and login, session-aware routing, a short onboarding introduction, and an authenticated student dashboard. The dashboard searches published student guidance and previews verified help contacts through existing backend APIs. Full article browsing/detail, Help Directory, assistant, document, and complaint workflows are not implemented in the frontend.

## Source layout

- `src/app`: application router and cross-cutting theme provider.
- `src/app/auth`: session provider, route guards, session errors, and tab-local onboarding marker.
- `src/features/auth`: registration/login forms and safe error mapping.
- `src/features/onboarding`: non-persistent welcome introduction.
- `src/features/application`: authenticated entry shell.
- `src/features/landing`: public landing and not-found pages.
- `src/shared/components`: brand, buttons, status badges/panels, and section heading.
- `src/shared/layout`: responsive site header, main layout, footer.
- `src/shared/theme`: theme preference control.
- `src/api`: fetch client, normalized API errors, authentication, liveness, student guidance search, and verified support contracts.
- `src/styles`: semantic design tokens and global responsive styling.

Keep business behavior in a feature as it is introduced. Keep API types close to the API module that owns them. Do not duplicate backend authorization decisions in the browser.

## Routing and application states

`BrowserRouter` routes `/`, `/register`, `/login`, `/onboarding`, and `/app`. Unauthenticated access to `/app` redirects to `/login`; authenticated access to `/login` or `/register` goes to onboarding or `/app`. `/app` requires the real `/auth/me` identity and the current tab's onboarding marker. Unknown paths explain that the page is unavailable and link home. The development and production host must serve `index.html` for unknown paths.

## Authentication and session

`AuthProvider` distinguishes loading, authenticated, unauthenticated, and session-error states. At startup it calls `GET /api/v1/auth/me`; it never treats local storage or a frontend token as evidence of authentication. A successful login calls `POST /auth/login` and then fetches `/auth/me` before navigation. The backend stores an opaque session in Redis and sets it in the HttpOnly `lexaware_session` cookie. The browser UI receives only the public profile fields from `/me` (`id`, email, display name, roles, status, and expiry). A 401 from an API request clears the in-memory session, and the expiry timestamp schedules a session recheck.

Registration sends exactly `{email, password, display_name?}` to `POST /auth/register`. Display name is optional; backend validation requires a 12–128 character password and applies an additional common-password check. Registration returns the backend's generic acknowledgment and does not establish a session. Duplicate addresses intentionally receive the same external response, so the UI does not claim to detect duplicates. Password recovery and email verification are not supported by the inspected backend and are not advertised.

Logout first calls `GET /auth/csrf`, then `POST /auth/logout` with the returned token in `X-CSRF-Token` and browser cookies included. Frontend session state clears only after the server logout succeeds (or reports that the session is already invalid). A network/CSRF failure leaves the user signed in and offers a retry.

The backend configures credentialed CORS for its exact `WEB_APP_URL`. Local development uses the same `localhost` site for Vite and the API. Production must use HTTPS (the backend sets `Secure` cookies in production) and a deployment layout where the `SameSite=Lax` cookies are sent with credentialed requests. `VITE_*` values are public build-time configuration and must never contain credentials or API secrets.

## Onboarding boundary

The backend has no onboarding-completion field or endpoint. The short, skippable introduction asks for no personal information and makes no server-persistence claim. Completion is stored in `sessionStorage`, keyed by the backend user ID, only for this browser tab. It is a navigation convenience, not account state; a new tab/device can show onboarding again. Move persistence to a backend contract when one exists.

## Design system

`src/styles/tokens.css` provides semantic surface, text, border, interaction, focus, spacing, radius, and typography tokens. Light values follow the approved palette. Dark mode maps the semantic layer to purpose-built dark surfaces and readable text; components consume the semantic layer rather than inverting colors. See [accessibility and responsive behavior](./accessibility.md).

## API boundary

`VITE_API_BASE_URL` configures the versioned API prefix; local development defaults to `http://localhost:8000/api/v1`. The client includes cookies (`credentials: include`), JSON-encodes ordinary request bodies, adds the existing `lexaware_csrf` double-submit token on unsafe requests, supports abort and finite timeout behavior, and normalizes both FastAPI `detail` responses and the assistant's `{error:{code,message}}` envelope. It preserves field details and `X-Correlation-ID` when present. It does not invent endpoint contracts or apply client-side role checks.

The API modules cover auth, `GET /health` (liveness), `GET /knowledge/articles` with a bounded student-audience search, and `GET /help?limit=3` for the dashboard's verified-contact preview. Search text remains in component memory, is not persisted, and is cancellable on unmount. The browser presents source links only for HTTP(S) URLs. Help actions use backend-validated contact data and the response's `verified_current` contract. Activity, saved-item, and announcement endpoints are absent; the dashboard says so rather than manufacturing content. `/ready` exposes infrastructure state and is not used as a browser health indicator. Feature API modules should be added alongside the corresponding product feature when that UI is implemented.

The authenticated shell uses a compact floating horizontal header rather than a persistent sidebar. Actions without frontend routes are non-interactive and labelled as coming soon. The dashboard's lightweight shield/book mark is layered SVG with CSS perspective and pointer-limited rotation; it has no WebGL, canvas, third-party 3D dependency, or continuous render loop. The static vector remains visible with reduced motion, which disables the transform and entrance animation. Responsive layouts stack the hero and actions and keep the support preview in normal document flow.

## Configuration and build

From `apps/web`, run `npm install`, copy `.env.example` to `.env.local` if the API URL differs, then run `npm run dev`. The default API URL is `http://localhost:8000/api/v1`; the backend must allow the Vite origin with credentialed CORS. `npm run build`, `npm run typecheck`, `npm run lint`, and `npm test` are the local quality gates. `npm run test:e2e` requires a running local API and database/Redis plus an installed Chromium-compatible browser; it creates a synthetic development account, so use a disposable development database. Browser routes require host-side SPA fallback in deployment.
