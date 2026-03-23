## 1. Feature Overview

* Name: Analytics (New Users)
* Summary: Simple endpoint returning count of recently registered active users.
* Purpose: Lightweight growth indicator.
* Business value: Basic KPI for onboarding trend visibility.

## 2. Current Implementation

* How it works today: `analytics/views.py` calls `GetNewUsersUseCase` with 7-day lookback intent.
* Main flows: compute reference datetime and count matching users.
* Entry points (routes, handlers, jobs): `GET /analytics/new-users/`.
* Key files involved (list with paths):
  * `analytics/views.py`
  * `analytics/application/use_cases/get_new_users.py`

## 3. Architecture & Design

* Layers involved (frontend/backend): view -> use case -> ORM count.
* Data flow (step-by-step): calculate `date_joined` threshold -> query user count -> JSON output.
* External integrations: none.
* State management (if applicable): read-only metric.

## 4. Data Model

* Entities involved: Django `User`.
* Database tables / schemas: `auth_user`.
* Relationships: none required.
* Important fields: `is_active`, `date_joined`.

## 5. Business Rules

* Explicit rules implemented in code: only active users counted.
* Edge cases handled: none.
* Validation logic: none (GET-only).

## 6. User Flows

* Normal flow: authorized financial user requests new-user metric.
* Error flow: unauthorized users blocked by decorator.
* Edge cases: zero users returns zero count.

## 7. API / Interfaces

* Endpoint: `GET /analytics/new-users/`.
* Input/output: no input body; output `{new_users: <int>}`.
* Contracts: serializer wraps response schema.
* Internal interfaces: uses injectable datetime/timedelta classes for tests.

## 8. Problems & Limitations

* Technical debt: query uses exact equality on `date_joined` (`date_joined=date_now_minus_7_days`) instead of range, likely undercounting.
* Bugs or inconsistencies: metric name implies last 7 days but implementation checks one exact timestamp.
* Performance issues: negligible.
* Missing validations: none.

## 9. Security Concerns ⚠️

* Any suspicious behavior: none.
* External code execution: none.
* Unsafe patterns: none significant.
* Injection risks: low.
* Hardcoded secrets: none.
* Unsafe file/system access: none.

## 10. Improvement Opportunities

* Refactors: change filter to `date_joined__gte` for true rolling window.
* Architecture improvements: expand analytics module with time-bucketed metrics.
* Scalability: add cached KPI snapshots if expanded.
* UX improvements: return trend delta vs previous window.

## 11. Acceptance Criteria

* Functional: endpoint returns active new-user count.
* Technical: count logic uses documented period semantics.
* Edge cases: empty result returns zero without errors.

## 12. Open Questions

* Unknown behaviors: expected timezone treatment for `date_joined` boundaries.
* Missing clarity in code: intended audience/permission scope beyond financial group.
* Assumptions made: this endpoint is currently a minimal MVP metric.
