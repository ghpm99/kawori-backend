## 1. Feature Overview

* Name: Authentication & Account Access
* Summary: JWT cookie auth, signup, password reset, email verification, and social OAuth account login/linking.
* Purpose: Control user identity lifecycle and session issuance.
* Business value: Enables secure access to all domain modules and reduces login friction via social providers.

## 2. Current Implementation

* How it works today: `authentication/views.py` delegates to use-case classes, sets HttpOnly JWT cookies, and writes audit logs for auth actions.
* Main flows: username/password login, token refresh/verify/signout, signup with default groups + budget bootstrap, password reset token lifecycle, email verification token lifecycle, social authorize/callback/link/unlink.
* Entry points (routes, handlers, jobs): `/auth/token/`, `/auth/token/refresh/`, `/auth/signup`, `/auth/password-reset/*`, `/auth/email/*`, `/auth/social/*`.
* Key files involved (list with paths):
  * `authentication/views.py`
  * `authentication/models.py`
  * `authentication/application/use_cases/*.py`
  * `authentication/utils.py`
  * `authentication/urls.py`

## 3. Architecture & Design

* Layers involved (frontend/backend): Backend Django views -> use cases -> Django ORM models; frontend receives cookies and redirect-based social callback.
* Data flow (step-by-step): Request JSON/query -> serializer/use-case validation -> model reads/writes (`UserToken`, `EmailVerification`, `SocialAuthState`, `SocialAccount`) -> JSON response or redirect with cookies.
* External integrations: OAuth token/profile HTTP calls (`requests`) to Google/Discord/GitHub/Facebook/Microsoft; mail enqueue through `mailer.utils`.
* State management (if applicable): Session state stored in JWT cookies + DB state for token/verification/social linking.

## 4. Data Model

* Entities involved: `User` (Django), `UserToken`, `EmailVerification`, `SocialAuthState`, `SocialAccount`.
* Database tables / schemas: `auth_user_token`, `auth_email_verification`, `auth_social_auth_state`, `auth_social_account`.
* Relationships: User 1:N tokens; User 1:1 email verification; User 1:N social states; User 1:N social accounts.
* Important fields: hashed token/state, expiry timestamps, `used` flags, provider identities, profile metadata JSON.

## 5. Business Rules

* Explicit rules implemented in code: token hashing via SHA-256; reset/verification token invalidation on new token issue; per-IP and per-user token rate limits; social link forbidden without authenticated user; cannot unlink last login method if no password.
* Edge cases handled: invalid/missing JSON; invalid/expired token/state; provider disabled/missing credentials; social account already linked to another user.
* Validation logic: required signup/reset fields, Django password validators, provider + mode checks, active-user checks.

## 6. User Flows

* Normal flow: Login/signup/social callback -> auth cookies set -> protected endpoints accessed via `validate_user`.
* Error flow: Invalid credentials/token/provider -> 4xx with message; callback returns error payload or redirect query params.
* Edge cases: Nonexistent email for reset returns generic success text to reduce enumeration; social callback handles provider errors and state replay.

## 7. API / Interfaces

* Endpoints:
  * `POST /auth/token/`, `POST /auth/token/verify/`, `POST /auth/token/refresh/`, `GET /auth/signout`
  * `POST /auth/signup`, `GET /auth/csrf/`
  * `POST /auth/password-reset/request/`, `GET /auth/password-reset/validate/`, `POST /auth/password-reset/confirm/`
  * `POST /auth/email/verify/`, `POST /auth/email/resend-verification/`
  * `GET /auth/social/providers/`, `GET /auth/social/<provider>/authorize/`, `GET /auth/social/<provider>/callback/`
  * `GET /auth/social/accounts/`, `POST /auth/social/accounts/<provider>/unlink/`
* Input/output: JSON bodies and query params; callback may return redirect with status params.
* Contracts: Auth tokens primarily cookie-based (`access_token`, `refresh_token`, `lifetimetoken`), not bearer header-first.
* Internal interfaces: use-case classes receive dependency-injected functions/models for testability.

## 8. Problems & Limitations

* Technical debt: duplicated serializer `.is_valid(raise_exception=False)` without strict error usage in several handlers.
* Bugs or inconsistencies: login failure returns HTTP 404 instead of common 401/403; some generic `except Exception` paths hide causes.
* Performance issues: synchronous social-provider HTTP requests in request path.
* Missing validations: no explicit CSRF enforcement logic in these POST views beyond middleware-level behavior.

## 9. Security Concerns ⚠️

* Any suspicious behavior: callback and provider integrations trust third-party response payloads with minimal schema validation.
* External code execution: none observed.
* Unsafe patterns: broad `except Exception` blocks can suppress security-relevant failures; social redirect URI is caller-provided (stored in `SocialAuthState`) and later used for redirect.
* Injection risks: low SQL injection risk here (ORM-only), but open redirect risk should be reviewed for `frontend_redirect_uri`.
* Hardcoded secrets: no direct hardcoded API keys in app code; env-driven.
* Unsafe file/system access: none in this feature.

## 10. Improvement Opportunities

* Refactors: centralize auth error model and HTTP status conventions; reduce duplicated cookie-setting logic.
* Architecture improvements: enforce strict serializer validation everywhere and typed DTOs for provider payloads.
* Scalability: async background for social profile fetching or circuit-breaker/retry policy.
* UX improvements: consistent localized error contracts and recovery hints for expired social state.

## 11. Acceptance Criteria

* Functional: user can signup/login/logout/refresh/reset password/verify email/social login-link-unlink.
* Technical: all token/state records are hashed, expirable, and one-time consumable.
* Edge cases: rate limits applied, generic response on unknown reset email, invalid social state rejected.

## 12. Open Questions

* Unknown behaviors: exact allowed redirect domains for `frontend_redirect_uri` are not enforced in this module.
* Missing clarity in code: expected auth status codes for invalid credentials are inconsistent with common standards.
* Assumptions made: mail queue workers are running to deliver reset/verification emails.
