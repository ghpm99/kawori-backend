## 1. Feature Overview

* Name: Audit & Release Script Observability
* Summary: request-level audit logging decorators, audit query/report APIs, AI-generated audit insights, and release-script execution tracking.
* Purpose: Improve traceability, compliance, and operational visibility.
* Business value: Supports incident analysis and controlled release operations.

## 2. Current Implementation

* How it works today: decorators capture request metadata and persist `AuditLog`; report endpoints aggregate events; release runner stores `ReleaseScriptExecution` records.
* Main flows: endpoint decorated -> sanitized request detail persisted with result; admins query logs/stats/report; release command executes pending scripts up to target version.
* Entry points (routes, handlers, jobs): `/audit/`, `/audit/stats/`, `/audit/report/`, `manage.py run_release_scripts`.
* Key files involved (list with paths):
  * `audit/decorators.py`
  * `audit/models.py`
  * `audit/views.py`
  * `audit/application/use_cases/*.py`
  * `audit/ai_assist.py`
  * `audit/release_scripts.py`
  * `audit/management/commands/run_release_scripts.py`

## 3. Architecture & Design

* Layers involved (frontend/backend): decorators + API views + use-case aggregations + management command orchestration.
* Data flow (step-by-step): incoming request -> sanitize body/query -> call wrapped view -> log success/failure/error with metadata; report API aggregates by dimensions and optionally generates AI insights.
* External integrations: optional AI insights via central AI service.
* State management (if applicable): persistent audit event stream and release execution history.

## 4. Data Model

* Entities involved: `AuditLog`, `ReleaseScriptExecution`.
* Database tables / schemas: `audit_log`, `release_script_execution`.
* Relationships: optional foreign key to user in audit log.
* Important fields: action/category/result/user/ip/path/method/detail/response_status and release script status/output timestamps.

## 5. Business Rules

* Explicit rules implemented in code: sensitive fields (password/token/secret) masked before logging; auth decorator attempts username/email/token-based user resolution for logs; release runner skips already successful scripts unless `--force`.
* Edge cases handled: invalid registry XML raises value error; dry-run mode prints pending scripts only.
* Validation logic: report filters normalize dates and cap limits (1..100).

## 6. User Flows

* Normal flow: admin accesses audit endpoints to inspect trends and failures.
* Error flow: wrapped endpoint exception still creates `result=error` audit record then re-raises.
* Edge cases: release script not found triggers command error before execution.

## 7. API / Interfaces

* Endpoints: `GET /audit/`, `GET /audit/stats/`, `GET /audit/report/`.
* Input/output: query filters for category/action/result/user/date range and pagination.
* Contracts: report response includes summary + breakdowns + optional `ai_insights` block.
* Internal interfaces: release registry source is `scripts.xml` parsed by `audit/release_scripts.py`.

## 8. Problems & Limitations

* Technical debt: decorator-based logging depends on consistent endpoint decoration coverage.
* Bugs or inconsistencies: auth user resolution heuristics may misattribute some attempts.
* Performance issues: high-volume logging and aggregation queries may need partitioning/index tuning.
* Missing validations: request detail can still contain large bodies (truncated but potentially noisy).

## 9. Security Concerns ⚠️

* Any suspicious behavior: release runner executes management command names from `scripts.xml` (controlled source, but still privileged).
* External code execution: yes, controlled internal command execution via `call_command` in release runner.
* Unsafe patterns: XML parsing on local file (`ElementTree`); currently wrapped and validated but integrity of `scripts.xml` is critical.
* Injection risks: low for SQL (ORM aggregations), but command execution registry must be protected in code review.
* Hardcoded secrets: none.
* Unsafe file/system access: reads registry path from settings and executes referenced scripts.

## 10. Improvement Opportunities

* Refactors: central policy for mandatory decorator coverage by endpoint class.
* Architecture improvements: append-only audit pipeline with asynchronous writes.
* Scalability: data retention tiers and archive strategy for audit logs.
* UX improvements: predefined report templates for common investigations.

## 11. Acceptance Criteria

* Functional: audit logs persist for decorated endpoints; admin can query stats/report; release scripts command executes pending entries.
* Technical: sensitive fields are masked and log write failures do not crash business endpoint.
* Edge cases: dry-run and force flags behave as documented.

## 12. Open Questions

* Unknown behaviors: retention and purge policy for audit tables is not codified.
* Missing clarity in code: governance process for who can edit `scripts.xml` in release branches.
* Assumptions made: only trusted maintainers can merge release registry changes.
