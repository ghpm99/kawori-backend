## 1. Feature Overview

* Name: Payment Management
* Summary: CRUD-like payment operations, payoff flow, monthly aggregation, bank statement view, CSV import pipeline, and AI-assisted import reconciliation.
* Purpose: Manage individual financial payment records linked to invoices.
* Business value: Core operational ledger for accounts payable/receivable and import automation.

## 2. Current Implementation

* How it works today: `payment/views.py` exposes endpoints backed by use-case classes for listing, detail updates, payoff, statement, and CSV/AI import flows.
* Main flows: manual payment create/update/payoff; statement generation; CSV map->normalize->reconcile->resolve->queue import->process command.
* Entry points (routes, handlers, jobs): `/financial/payment/*` endpoints plus management command `financial.management.commands.process_imported_payments`.
* Key files involved (list with paths):
  * `payment/views.py`
  * `payment/models.py`
  * `payment/utils.py`
  * `payment/ai_features.py`
  * `payment/ai_assist.py`
  * `payment/application/use_cases/*.py`
  * `financial/management/commands/process_imported_payments.py`

## 3. Architecture & Design

* Layers involved (frontend/backend): API view layer -> use cases -> domain models (`Payment`, `ImportedPayment`) + helpers.
* Data flow (step-by-step):
  * Manual flow: request -> validate -> create/update `Payment` -> adjust related invoice totals.
  * CSV flow: map CSV headers/rows -> parse + validate row -> find exact/fuzzy matches -> optional AI suggestion -> create/update `ImportedPayment` queue records.
  * Processing flow: background command claims queued imports, optionally normalizes via AI, merges into existing payment or creates new invoice/payments.
* External integrations: AI task execution via `ai.assist` and prompt service.
* State management (if applicable): `ImportedPayment.status` transitions (`pending`/`queued`/`processing`/`completed`/`failed`) and AI idempotency keys.

## 4. Data Model

* Entities involved: `Payment`, `ImportedPayment`, related `Invoice`, `Tag`, `User`.
* Database tables / schemas: `financial_payment`, `financial_imported_payment`, M2M `ImportedPayment.raw_tags`.
* Relationships: payment belongs to invoice and user; imported payment may reference matched payment and many tags.
* Important fields: payment type/status/date/value/reference; imported strategy/source/status/AI suggestion data/normalization data.

## 5. Business Rules

* Explicit rules implemented in code: payment type inferred from import source/sign; generated reference hash when missing; imported items can be edited only in `pending` or `failed`; budget-tag presence required before queueing import.
* Edge cases handled: malformed JSON; invalid import type; duplicate reference per user blocked by unique constraint; merge-group tag propagation.
* Validation logic: row-level amount/date/installment checks; statement date-range serializer validation; payment payoff protects already-paid records.

## 6. User Flows

* Normal flow:
  * User lists/filters payments and updates details.
  * User uploads CSV and gets parsed matches.
  * User confirms tags/import actions.
  * Processor command materializes final invoice/payment updates.
* Error flow: invalid payloads return 400; missing payment/invoice context returns 404/400; non-editable imports skipped.
* Edge cases: uncertain fuzzy-match confidence triggers capped AI suggestions with per-request and per-day limits.

## 7. API / Interfaces

* Endpoints:
  * `GET /financial/payment/`, `POST /financial/payment/new/`, `GET /financial/payment/<id>/`, `POST /financial/payment/<id>/save`, `POST /financial/payment/<id>/payoff`
  * `GET /financial/payment/month/`, `GET /financial/payment/scheduled`
  * `GET /financial/payment/statement/`, `GET /financial/payment/statement/anomalies`
  * `POST /financial/payment/csv-mapping/`, `POST /financial/payment/process-csv/`
  * `POST /financial/payment/csv-ai-map/`, `POST /financial/payment/csv-ai-normalize/`, `POST /financial/payment/csv-ai-reconcile/`, `POST /financial/payment/ai-tag-suggestions/`
  * `POST /financial/payment/csv-resolve-imports/`, `POST /financial/payment/csv-import/`
* Input/output: JSON-based contracts with mapped transaction objects and match metadata.
* Contracts: use-case responses typically return `{payload,error}` style for view translation.
* Internal interfaces: management command consumes queued `ImportedPayment` records.

## 8. Problems & Limitations

* Technical debt: mixed legacy and new patterns for error shape/status codes.
* Bugs or inconsistencies: some failures return generic `Payment not found` with status 500; `save_new_payment` can return success even when `installments <= 0`.
* Performance issues: heavy Python matching loops and historical scans during CSV processing.
* Missing validations: some serializer validations are non-blocking (`is_valid(raise_exception=False)`) and then manually inferred.

## 9. Security Concerns ⚠️

* Any suspicious behavior: import processing command updates multiple records with broad exception handling.
* External code execution: none direct, but AI calls send transaction/user metadata to external providers.
* Unsafe patterns: command prints raw exceptions; extensive `except Exception` branches may mask data integrity issues.
* Injection risks: low SQL injection risk in payment module itself (mostly ORM).
* Hardcoded secrets: none in module code.
* Unsafe file/system access: none direct; indirect risk via unbounded JSON payload size in CSV endpoints.

## 10. Improvement Opportunities

* Refactors: unify response/error protocol and status codes; centralize payment/invoice value recalculation.
* Architecture improvements: offload CSV parsing + matching to async jobs; add deterministic retry workflow.
* Scalability: index tuning for reference/date/user matching; incremental import windows.
* UX improvements: richer reconciliation explanations and deterministic conflict resolution UI hints.

## 11. Acceptance Criteria

* Functional: CRUD/payoff/statement and CSV import pipeline operate end-to-end.
* Technical: imported status transitions are valid and idempotency keys prevent duplicate AI suggestions.
* Edge cases: duplicate references, missing tags, non-editable rows, and invalid dates are handled predictably.

## 12. Open Questions

* Unknown behaviors: expected trigger/schedule for `process_imported_payments` command is not documented in code.
* Missing clarity in code: business meaning of `split` strategy in imports is not fully materialized in command paths.
* Assumptions made: invoice/tag domain invariants are enforced elsewhere when imports create new records.
