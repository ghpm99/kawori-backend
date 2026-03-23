## 1. Feature Overview

- Name: Audit Logging & Reporting
- Summary: Records authenticated actions and provides audit log search, stats, and AI-assisted incident insights.
- Target user: Admin users.
- Business value: Enables traceability, operational visibility, and compliance evidence.

## 2. Problem Statement

- Admins need action-level evidence and trend monitoring.
- Without audit logs, root-cause analysis and accountability are weak.

## 3. Current Behavior

- Decorators capture request metadata (user, IP, path, method, sanitized details, result status).
- Captures auth actions (`login`, `logout`, token operations, etc.) and domain actions.
- `GET /audit/` returns filtered paginated logs.
- `GET /audit/stats/` returns by-category and by-result aggregates for last 24h and 7d.
- `GET /audit/report/` returns summary, trend buckets, top actions/categories/users, failures by action.
- Audit report optionally includes AI insights when activity signal threshold is met.

## 4. User Flows

### 4.1 Main Flow

1. User performs auditable action.
2. Decorator writes audit record.
3. Admin queries logs/report endpoints.

### 4.2 Alternative Flows

1. Admin requests scoped report (category/action/user/date range).
2. System enriches report with AI incident hypotheses and recommendations.

### 4.3 Error Scenarios

- If logging write fails, primary request still proceeds (`_create_audit_log_safe`).
- Invalid date filters are ignored or defaulted by parser behavior.

## 5. Functional Requirements

- The system must persist action-level audit records.
- The admin can filter and paginate logs.
- The system should provide aggregate and AI-enriched report views.

## 6. Business Rules

- Result values: `success`, `failure`, `error`.
- Sensitive fields in payload (`password`, `token`, etc.) are masked.
- AI insights executed only when event/failure/anomaly thresholds are met.

## 7. Data Model (Business View)

- `AuditLog`: action, category, result, actor context, target context, request detail, response status, timestamp.

## 8. Interfaces

- APIs: `/audit/`, `/audit/stats/`, `/audit/report/`.

## 9. Dependencies

- Depends on decorators applied across modules.
- AI insights depend on AI feature availability and prompt service.

## 10. Limitations / Gaps

- Coverage depends on endpoints being decorated; undecorated actions are not audited.
- Some modules still expose non-audited read endpoints.

## 11. Opportunities

- Add immutable export snapshot for compliance evidence.
- Add per-action SLA/alerting on failure spikes.

## 12. Acceptance Criteria

- Given an auditable endpoint call, when it completes, then an audit log is created with result and metadata.
- Given admin filters, when querying `/audit/`, then matching paginated logs are returned.
- Given sufficient report signal, when querying `/audit/report/`, then AI insights are included.

## 13. Assumptions

- Admin role assignment is maintained externally by group governance.
