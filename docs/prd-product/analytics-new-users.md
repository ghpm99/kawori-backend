## 1. Feature Overview

- Name: New User Analytics Snapshot
- Summary: Returns count of new active users for a recent window.
- Target user: Financial group users consuming dashboard analytics.
- Business value: Basic growth signal for product usage.

## 2. Problem Statement

- Teams need a lightweight user growth indicator.
- Without it, dashboards miss basic adoption trend signal.

## 3. Current Behavior

- `GET /analytics/new-users/` computes `date_joined = now - 7 days` and counts active users with exact match on that timestamp.

## 4. User Flows

### 4.1 Main Flow

1. Authorized user requests new-users endpoint.
2. System returns integer `new_users`.

### 4.2 Alternative Flows

- None implemented.

### 4.3 Error Scenarios

- Invalid token/group permission blocks access.

## 5. Functional Requirements

- The system must return numeric `new_users` metric.

## 6. Business Rules

- Access requires `financial` group.
- Current code uses equality filter instead of range filter.

## 7. Data Model (Business View)

- `User`: `is_active`, `date_joined`.

## 8. Interfaces

- API: `/analytics/new-users/`.

## 9. Dependencies

- Depends on Django auth users.

## 10. Limitations / Gaps

- Exact timestamp equality likely undercounts almost always.
- No configurable lookback period.

## 11. Opportunities

- Change filter to `date_joined__gte now-7d`.
- Add period parameter and grouped trend series.

## 12. Acceptance Criteria

- Given authorized user, when endpoint is called, then a JSON payload with `new_users` number is returned.

## 13. Assumptions

- Current endpoint is intended as a simplified metric and may require correction.
