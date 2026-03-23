## 1. Feature Overview

* Name: Invoice Management
* Summary: Invoice listing/detail/update/create, invoice-payment listing, and invoice-tag assignment.
* Purpose: Manage grouped payment obligations and their lifecycle state.
* Business value: Keeps payable/receivable bundles organized and auditable.

## 2. Current Implementation

* How it works today: `invoice/views.py` routes to use-case classes for query filtering, creation, detail updates, and tag updates.
* Main flows: create invoice -> auto-generate installment payments; update invoice metadata; attach/detach tags; list child payments.
* Entry points (routes, handlers, jobs): `/financial/invoice/`, `/financial/invoice/new/`, `/financial/invoice/<id>/`, `/financial/invoice/<id>/save/`, `/financial/invoice/<id>/payments/`, `/financial/invoice/<id>/tags`.
* Key files involved (list with paths):
  * `invoice/views.py`
  * `invoice/models.py`
  * `invoice/application/use_cases/*.py`
  * `invoice/utils.py`
  * `invoice/urls.py`

## 3. Architecture & Design

* Layers involved (frontend/backend): View -> use case -> ORM + shared utility (`financial.utils.generate_payments`).
* Data flow (step-by-step): request filters/payload -> use-case validation -> invoice/tag/payment ORM operations -> JSON response.
* External integrations: none direct.
* State management (if applicable): invoice `status`, `value`, `value_open`, `value_closed`, and payment_date tracking.

## 4. Data Model

* Entities involved: `Invoice`, `Payment`, `Tag`, `Contract`, `User`.
* Database tables / schemas: `financial_invoice`, `financial_payment`, invoice-tag M2M join table.
* Relationships: invoice belongs to user and optional contract; invoice has many payments and many tags.
* Important fields: type/status/installments/payment_date/fixed/value and validation status helpers.

## 5. Business Rules

* Explicit rules implemented in code: required fields for invoice creation; tag ownership must match user; invoice values split into generated installment payments.
* Edge cases handled: invalid type string rejected (`credit` or `debit` expected); invoice not found returns 404.
* Validation logic: dedicated `validate_invoice_data` enforces financial consistency invariants (sum decomposition, status/value coherence).

## 6. User Flows

* Normal flow: user creates invoice with tags -> system creates payments -> user can query invoice and payments.
* Error flow: invalid fields/tags/type produce 400; missing invoice returns 404.
* Edge cases: inactive invoices excluded in many read paths; optional payload fields in updates are patch-like.

## 7. API / Interfaces

* Endpoints:
  * `GET /financial/invoice/`
  * `POST /financial/invoice/new/`
  * `GET /financial/invoice/<id>/`
  * `POST /financial/invoice/<id>/save/`
  * `GET /financial/invoice/<id>/payments/`
  * `POST /financial/invoice/<id>/tags`
* Input/output: JSON request and structured list/detail response payloads.
* Contracts: invoice query supports status/type/date/installment/fixed/activity filters.
* Internal interfaces: use cases receive helper fns (`parse_type`, `format_date`, `generate_payments`, pagination).

## 8. Problems & Limitations

* Technical debt: duplication with legacy invoice logic that still exists in `financial/views.py`.
* Bugs or inconsistencies: mixed status semantics (`value_open` checks vs explicit status field) across modules.
* Performance issues: repeated tag traversals and list materialization in Python for response building.
* Missing validations: some views call serializers with non-raising validation and continue.

## 9. Security Concerns ⚠️

* Any suspicious behavior: none overt.
* External code execution: none.
* Unsafe patterns: broad transaction blocks without explicit integrity error handling.
* Injection risks: low (ORM, no string-interpolated SQL in invoice module).
* Hardcoded secrets: none.
* Unsafe file/system access: none.

## 10. Improvement Opportunities

* Refactors: remove duplicated invoice business logic from `financial/views.py` and keep single module ownership.
* Architecture improvements: enforce stricter typed DTO validation in all endpoints.
* Scalability: prefetch optimizations for invoice->tags->payments in list endpoints.
* UX improvements: explicit invoice validation-state endpoint using `Invoice.validate_invoice` output.

## 11. Acceptance Criteria

* Functional: invoice create/read/update/tags/payments endpoints work for authenticated financial users.
* Technical: generated payment installments reconcile with invoice totals.
* Edge cases: invalid tags/type/payload return deterministic 4xx responses.

## 12. Open Questions

* Unknown behaviors: intended contract linkage for standalone invoices is not enforced as required.
* Missing clarity in code: authoritative source for invoice status (`status` vs `value_open`) needs standardization.
* Assumptions made: payment generation utility is canonical for all invoice creation paths.
