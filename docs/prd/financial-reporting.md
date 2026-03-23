## 1. Feature Overview

* Name: Financial Reporting & Metrics
* Summary: Analytical reporting endpoints for payment summaries, counts/amounts, forecast, metrics KPIs, cash flow, top expenses, balance projection, overdue health, tag evolution, and heuristic AI insights.
* Purpose: Provide decision-support analytics over financial transactions.
* Business value: Enables trend monitoring, risk detection, and planning.

## 2. Current Implementation

* How it works today: `financial/views.py` serves report endpoints mostly via use-case classes; several SQL-heavy reports use raw SQL/cursors.
* Main flows: period validation -> aggregate query execution -> response serialization.
* Entry points (routes, handlers, jobs): `/financial/report/*` routes from `financial/urls.py`.
* Key files involved (list with paths):
  * `financial/views.py`
  * `financial/application/use_cases/*.py`
  * `financial/ai_features.py`
  * `financial/urls.py`

## 3. Architecture & Design

* Layers involved (frontend/backend): view -> serializer/use case -> ORM/raw SQL.
* Data flow (step-by-step): parse period and filters -> execute report query (ORM or SQL) -> normalize numeric outputs -> serializer response.
* External integrations: none for core reports; AI insights are heuristic code (not external LLM).
* State management (if applicable): read-only analytics derived from payment/invoice/tag data and materialized SQL view `financial_paymentsummary`.

## 4. Data Model

* Entities involved: `Payment`, `Invoice`, `Tag`, `Contract`, `Month` (legacy).
* Database tables / schemas: `financial_payment`, `financial_invoice`, `financial_contract`, `financial_tag`, `financial_paymentsummary` (view/table assumed).
* Relationships: reports aggregate through invoice->tag and invoice->contract paths.
* Important fields: payment type/status/value/payment_date/active flags.

## 5. Business Rules

* Explicit rules implemented in code: date-range validations (`date_from <= date_to`); open/closed semantics map from payment status; overdue only counts open debit payments before reference date.
* Edge cases handled: configurable limits for top-expenses and projection horizons; previous-period comparison optional for tag evolution.
* Validation logic: dedicated query serializers for required/optional period filters.

## 6. User Flows

* Normal flow: user selects date range -> endpoint returns chart/table data and summaries.
* Error flow: invalid period query returns 400 with serializer message.
* Edge cases: no-data windows produce zeroed aggregates and fallback insight message.

## 7. API / Interfaces

* Endpoints:
  * `GET /financial/report/` (payment summary)
  * `POST /financial/report/ai-insights/`
  * `GET /financial/report/count_payment`, `amount_payment`, `amount_payment_open`, `amount_payment_closed`, `amount_invoice_by_tag`, `amount_forecast_value`
  * `GET /financial/report/metrics/`, `daily_cash_flow`, `top_expenses`, `balance_projection`, `overdue_health`, `tag_evolution`
* Input/output: query params and JSON payloads (insights POST accepts optional period payload).
* Contracts: multiple serializers define shape for each report family.
* Internal interfaces: use cases accept dependency-injected cursor/time helpers for testing.

## 8. Problems & Limitations

* Technical debt: `financial/views.py` still contains legacy non-report CRUD logic duplicated elsewhere.
* Bugs or inconsistencies: mixed ORM and raw SQL paths with differing semantics may drift.
* Performance issues: some reports execute raw SQL without pagination or caching.
* Missing validations: dependence on existing SQL view/table `financial_paymentsummary` without startup checks.

## 9. Security Concerns ⚠️

* Any suspicious behavior: raw SQL usage is extensive; parameterized placeholders are used but surface area is higher.
* External code execution: none.
* Unsafe patterns: broad direct cursor access across many endpoints increases maintenance risk.
* Injection risks: currently mitigated by parameter binding, but manual SQL expansion is still a risk vector.
* Hardcoded secrets: none.
* Unsafe file/system access: none.

## 10. Improvement Opportunities

* Refactors: split legacy CRUD code out of `financial/views.py` entirely.
* Architecture improvements: unify on ORM/query-builder or isolate SQL in repository layer.
* Scalability: add caching/materialization strategy for expensive report queries.
* UX improvements: consistent metadata (`period`, `units`, `precision`) across all report responses.

## 11. Acceptance Criteria

* Functional: all reporting endpoints return deterministic aggregates for valid date filters.
* Technical: serializer validations block invalid periods and keep response schemas stable.
* Edge cases: empty periods and compare-with-previous toggles behave predictably.

## 12. Open Questions

* Unknown behaviors: exact refresh process for `financial_paymentsummary` source is not defined in module.
* Missing clarity in code: ownership boundary between `financial` and specialized apps (`payment`, `invoice`, `contract`) remains blurred.
* Assumptions made: underlying SQL objects and indexes exist in production DB.
