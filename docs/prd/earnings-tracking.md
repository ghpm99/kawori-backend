## 1. Feature Overview

* Name: Earnings Tracking
* Summary: Read-only listing/filtering of credit payments as earnings.
* Purpose: Separate revenue visualization from general payment listing.
* Business value: Simplifies income monitoring and reporting UI.

## 2. Current Implementation

* How it works today: `earnings/views.py` delegates to `GetAllEarningsUseCase` which filters `Payment` by credit type.
* Main flows: query earnings by status/date/name/contract/fixed/active filters with pagination.
* Entry points (routes, handlers, jobs): `GET /financial/earnings/`.
* Key files involved (list with paths):
  * `earnings/views.py`
  * `earnings/application/use_cases/get_all_earnings.py`

## 3. Architecture & Design

* Layers involved (frontend/backend): thin view -> use case -> ORM query.
* Data flow (step-by-step): parse query params -> build filter dict -> paginate queryset -> map response rows.
* External integrations: none.
* State management (if applicable): read-only projections from payment table.

## 4. Data Model

* Entities involved: `Payment` with related invoice/contract.
* Database tables / schemas: `financial_payment` (+ joins to invoice/contract).
* Relationships: payment belongs to invoice which belongs to contract.
* Important fields: type/status/payment_date/value and contract metadata.

## 5. Business Rules

* Explicit rules implemented in code: baseline filter enforces `type = credit`; optional status mapping (`open`/`done`).
* Edge cases handled: invalid/missing date filters fallback to wide defaults.
* Validation logic: query parsing uses helpers from `kawori.utils`.

## 6. User Flows

* Normal flow: user requests earnings list and navigates paginated results.
* Error flow: malformed values usually fallback silently rather than fail.
* Edge cases: `type` query can override default credit filter (potentially exposing non-earnings).

## 7. API / Interfaces

* Endpoints: `GET /financial/earnings/`.
* Input/output: query params and paginated JSON list.
* Contracts: response includes contract id/name derived from payment invoice relation.
* Internal interfaces: shared pagination and boolean/date helpers.

## 8. Problems & Limitations

* Technical debt: no dedicated model for earnings; hardcoded payment-type interpretation.
* Bugs or inconsistencies: allowing request `type` to override default may violate feature intent.
* Performance issues: relies on runtime joins for each row.
* Missing validations: no strict parameter validation serializer.

## 9. Security Concerns ⚠️

* Any suspicious behavior: none.
* External code execution: none.
* Unsafe patterns: permissive filter parsing can produce unexpected outputs.
* Injection risks: low.
* Hardcoded secrets: none.
* Unsafe file/system access: none.

## 10. Improvement Opportunities

* Refactors: enforce immutable credit-only filter in earnings endpoint.
* Architecture improvements: move shared filter parser to common module with serializers.
* Scalability: select_related/prefetch tuning for contract lookups.
* UX improvements: add totals summary by period/status.

## 11. Acceptance Criteria

* Functional: authenticated financial user can query earnings list with pagination.
* Technical: endpoint returns only owned payment records.
* Edge cases: invalid page/filter values do not crash endpoint.

## 12. Open Questions

* Unknown behaviors: whether debit rows should ever be visible in earnings endpoint.
* Missing clarity in code: target reporting granularity (daily/monthly) for earnings module.
* Assumptions made: contract relation exists for all relevant earning payments.
