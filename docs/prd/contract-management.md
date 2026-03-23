## 1. Feature Overview

* Name: Contract Management
* Summary: Contract CRUD-lite, contract-invoice listing, invoice inclusion under contract, contract merge, and recalculation routines.
* Purpose: Group invoices into long-lived financial agreements.
* Business value: Enables portfolio-level tracking of open/closed contract balances.

## 2. Current Implementation

* How it works today: `contract/views.py` calls use cases for create/list/detail/invoice inclusion/merge/update-values.
* Main flows: create contract, attach new invoices (with generated payments), merge contracts and migrate invoices, recompute totals.
* Entry points (routes, handlers, jobs): `/financial/contract/`, `/financial/contract/new`, `/financial/contract/<id>/...`, `/financial/contract/update_all_contracts_value`.
* Key files involved (list with paths):
  * `contract/views.py`
  * `contract/models.py`
  * `contract/application/use_cases/*.py`
  * `financial/utils.py`

## 3. Architecture & Design

* Layers involved (frontend/backend): view -> use case -> ORM.
* Data flow (step-by-step): input payload -> ownership checks -> contract/invoice writes in transaction -> optional recomputation.
* External integrations: none.
* State management (if applicable): contract aggregate fields (`value`, `value_open`, `value_closed`) updated from linked invoices.

## 4. Data Model

* Entities involved: `Contract`, `Invoice`, `Tag`, `Payment`, `User`.
* Database tables / schemas: `financial_contract`, `financial_invoice`, `financial_payment`.
* Relationships: contract 1:N invoices.
* Important fields: name and aggregate values split into open/closed amounts.

## 5. Business Rules

* Explicit rules implemented in code: only owner can mutate contract and attached invoices/tags; merge skips self; include-invoice validates user-owned tags.
* Edge cases handled: missing contract returns 404.
* Validation logic: tag list ownership count must match unique submitted tag ids.

## 6. User Flows

* Normal flow: create contract -> add invoice -> auto-generate payments -> contract value increases.
* Error flow: invalid contract/tag input returns 404/400.
* Edge cases: merge operation migrates invoices then deletes source contracts.

## 7. API / Interfaces

* Endpoints:
  * `GET /financial/contract/`, `POST /financial/contract/new`
  * `GET /financial/contract/<id>/`
  * `GET /financial/contract/<id>/invoices/`
  * `POST /financial/contract/<id>/invoice/`
  * `POST /financial/contract/<id>/merge/`
  * `POST /financial/contract/update_all_contracts_value`
* Input/output: JSON payloads and paginated contract/invoice structures.
* Contracts: merge request expects list field `contracts`.
* Internal interfaces: relies on shared helpers `generate_payments` and `update_contract_value`.

## 8. Problems & Limitations

* Technical debt: contract totals are mutable in multiple modules/commands, increasing drift risk.
* Bugs or inconsistencies: no explicit duplicate-contract-name guard.
* Performance issues: full recomputation loops can be expensive for large datasets.
* Missing validations: merge payload shape is weakly validated.

## 9. Security Concerns ⚠️

* Any suspicious behavior: none overt.
* External code execution: none.
* Unsafe patterns: broad transactions without explicit optimistic locking.
* Injection risks: low (ORM-only in this module).
* Hardcoded secrets: none.
* Unsafe file/system access: none.

## 10. Improvement Opportunities

* Refactors: centralize aggregate recalculation in one service.
* Architecture improvements: domain events when invoices/payments change.
* Scalability: incremental recalculation with SQL aggregates instead of iterative loops.
* UX improvements: pre-merge dry-run summary showing impacted invoices.

## 11. Acceptance Criteria

* Functional: contracts can be created, listed, detailed, merged, and invoice-associated.
* Technical: value fields remain consistent with active linked invoices.
* Edge cases: invalid ownership/tag references are rejected.

## 12. Open Questions

* Unknown behaviors: policy for deleting empty contracts is not explicit.
* Missing clarity in code: whether contract names must be unique per user.
* Assumptions made: financial health cron catches residual inconsistencies.
