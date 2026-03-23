## 1. Feature Overview

* Name: System Platform (Core Django Runtime)
* Summary: Global URL composition, middleware chain, cookie auth decorator, shared utility functions, and settings-driven environment configuration.
* Purpose: Provide foundational runtime behavior used by all domain features.
* Business value: Centralizes security/session/cors/media/static behavior across modules.

## 2. Current Implementation

* How it works today: `kawori/urls.py` mounts all domain apps; middleware in `kawori/middleware.py` handles CSRF cookie behavior and CORS; `kawori/decorators.py` enforces group-based access from JWT cookies.
* Main flows: request enters middleware -> endpoint decorator validates user token/group -> app view executes.
* Entry points (routes, handlers, jobs): root URL router `/` and all app prefixes.
* Key files involved (list with paths):
  * `kawori/urls.py`
  * `kawori/settings/base.py`
  * `kawori/middleware.py`
  * `kawori/decorators.py`
  * `kawori/utils.py`

## 3. Architecture & Design

* Layers involved (frontend/backend): Django middleware/routing/auth decorator base layer.
* Data flow (step-by-step): cookie token parsed -> JWT verified -> user/group validated -> domain view receives injected `user`.
* External integrations: static/media serving and optional Google Cloud Storage helper library.
* State management (if applicable): JWT cookies + DB-backed user/group state.

## 4. Data Model

* Entities involved: Django `User` and `Group` used by shared access decorator.
* Database tables / schemas: Django auth tables.
* Relationships: users mapped to groups for authorization gates.
* Important fields: cookie token names (`ACCESS_TOKEN_NAME`, `REFRESH_TOKEN_NAME`), group names used by endpoints.

## 5. Business Rules

* Explicit rules implemented in code: endpoints require explicit group name in `validate_user`; CORS allows only origins in configured frontend list; OPTIONS preflight handled by middleware.
* Edge cases handled: missing/invalid token returns 401; inactive or non-group user returns 403.
* Validation logic: JWT token type and signature checked via simplejwt token verification.

## 6. User Flows

* Normal flow: valid cookie and group membership -> authorized request passes.
* Error flow: token missing/invalid/inactive/wrong-group -> blocked with JSON error.
* Edge cases: origin filtering can reject requests with non-allowlisted origins.

## 7. API / Interfaces

* Endpoints: platform-level prefixes in `kawori/urls.py` (`/auth`, `/financial`, `/remote`, `/ai`, etc.).
* Input/output: cookie-driven auth contract across modules.
* Contracts: access depends on group names (`financial`, `admin`, `user`, `blackdesert`, `discord`).
* Internal interfaces: shared helpers `paginate`, `format_date`, `boolean` reused across many apps.

## 8. Problems & Limitations

* Technical debt: custom auth decorator duplicates behavior that could leverage DRF permissions more uniformly.
* Bugs or inconsistencies: CORS + custom origin middleware can produce overlapping behavior and confusion.
* Performance issues: repeated user lookup and group checks per request.
* Missing validations: no centralized rate limiting in core layer.

## 9. Security Concerns ⚠️

* Any suspicious behavior: CSRF cookie middleware writes `HTTP_X_CSRFTOKEN` directly from cookie, reducing header-origin distinction.
* External code execution: none.
* Unsafe patterns: group names are string literals distributed across modules; mis-typing can silently alter authorization intent.
* Injection risks: low in core utilities.
* Hardcoded secrets: none in code, but security depends on env cookie domain/origin settings.
* Unsafe file/system access: media/static exposed via settings; should be restricted in production.

## 10. Improvement Opportunities

* Refactors: migrate to unified DRF permission/authentication classes.
* Architecture improvements: centralized authorization policy map and per-endpoint permission tests.
* Scalability: cache user-group membership in request context/token claims.
* UX improvements: consistent platform-level error response schema.

## 11. Acceptance Criteria

* Functional: all registered app routes are reachable and protected by intended group checks.
* Technical: middleware enforces configured CORS/origin policy and JWT cookie validation remains consistent.
* Edge cases: invalid origin/token cases are rejected deterministically.

## 12. Open Questions

* Unknown behaviors: production reverse-proxy headers and trusted proxy chain assumptions are not fully documented.
* Missing clarity in code: interaction between CORS middleware and `OriginFilterMiddleware` in actual deployment stack.
* Assumptions made: environment variables for cookie domain and frontend origins are correctly configured per environment.
