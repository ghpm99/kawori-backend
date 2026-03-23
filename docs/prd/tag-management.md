## 1. Feature Overview

* Name: Tag Management
* Summary: User-owned financial tags with color metadata and aggregate statistics over invoices.
* Purpose: Categorize invoices/payments and support budget overlays.
* Business value: Drives reporting, budgeting, and reconciliation decisions.

## 2. Current Implementation

* How it works today: `tag/views.py` provides list/detail/create/update endpoints and delegates to use-case classes.
* Main flows: create unique tag per user, list tags with aggregate totals, update name/color.
* Entry points (routes, handlers, jobs): `/financial/tag/`, `/financial/tag/new`, `/financial/tag/<id>/`, `/financial/tag/<id>/save`.
* Key files involved (list with paths):
  * `tag/views.py`
  * `tag/models.py`
  * `tag/application/use_cases/*.py`

## 3. Architecture & Design

* Layers involved (frontend/backend): view -> use case -> ORM aggregation.
* Data flow (step-by-step): request -> uniqueness/validation checks -> ORM create/update/query -> response with aggregate values.
* External integrations: none.
* State management (if applicable): tag ordering prioritizes budget tags in list responses.

## 4. Data Model

* Entities involved: `Tag`, related `Invoice`, optional related `Budget`.
* Database tables / schemas: `financial_tag` (+ M2M with invoices via invoice app).
* Relationships: tag belongs to user; tag can be attached to many invoices; budget uses one-to-one with tag.
* Important fields: `name`, `color`, `user`.

## 5. Business Rules

* Explicit rules implemented in code: unique tag name per user; create rejects duplicates.
* Edge cases handled: missing tag id returns 404.
* Validation logic: create serializer enforces payload constraints.

## 6. User Flows

* Normal flow: user creates tag -> assigns tags on invoices -> tag aggregates shown in listing.
* Error flow: duplicate name or missing tag returns error.
* Edge cases: budget tags are prefixed with `#` in responses.

## 7. API / Interfaces

* Endpoints: `GET /financial/tag/`, `POST /financial/tag/new`, `GET /financial/tag/<id>/`, `POST /financial/tag/<id>/save`.
* Input/output: JSON payloads with `name` and `color`; list includes totals.
* Contracts: list supports `name__icontains` filter.
* Internal interfaces: use case uses `annotate` with `Count/Sum` over related invoices.

## 8. Problems & Limitations

* Technical debt: HTTP 404 used for duplicate tag in create flow (semantic mismatch).
* Bugs or inconsistencies: update path does not check uniqueness before renaming.
* Performance issues: aggregate query can grow with invoice volume.
* Missing validations: color format not strongly validated in use case layer.

## 9. Security Concerns ⚠️

* Any suspicious behavior: none.
* External code execution: none.
* Unsafe patterns: minimal.
* Injection risks: low.
* Hardcoded secrets: none.
* Unsafe file/system access: none.

## 10. Improvement Opportunities

* Refactors: enforce normalized unique name checks on update.
* Architecture improvements: move shared tag formatting rules to serializer/service.
* Scalability: precomputed aggregates for heavy dashboards.
* UX improvements: duplicate suggestion and color palette validation feedback.

## 11. Acceptance Criteria

* Functional: create/list/detail/update tags for authenticated financial user.
* Technical: uniqueness per user is preserved.
* Edge cases: non-owned tags cannot be accessed or changed.

## 12. Open Questions

* Unknown behaviors: whether soft-delete of tags is desired.
* Missing clarity in code: expected allowed color palette/format constraints.
* Assumptions made: invoice-tag relation integrity is managed by Django M2M.
