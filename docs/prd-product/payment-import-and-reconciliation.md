## 1. Feature Overview

- Name: CSV Import, Reconciliation & AI Assist
- Summary: Imports bank/card CSV rows, maps fields, validates rows, suggests matches/tags, stages imports, and converts staged rows into invoices/payments.
- Target user: Financial users importing external transaction data.
- Business value: Reduces manual bookkeeping effort and speeds reconciliation accuracy.

## 2. Problem Statement

- Manual transaction entry is slow and error-prone.
- Without this feature, high-volume import and reconciliation becomes operationally expensive.

## 3. Current Behavior

- CSV mapping endpoint returns heuristic mapping for headers.
- Upload processing parses rows, normalizes fields, validates, generates references, tries exact and fuzzy matching.
- AI is called only for uncertain candidate confidence bands and capped by per-request and per-day limits.
- Resolve imports stores `ImportedPayment` records with strategy (`merge`, `split`, `new`) and optional merge group.
- Import start endpoint requires tags; skips items without budget tag and queues eligible items.
- Background command `process_imported_payments` processes queued imports, merges with existing payment or creates new invoice/payment set.

## 4. User Flows

### 4.1 Main Flow

1. User uploads CSV headers/body.
2. System processes rows and returns mapped candidates with possible matches.
3. User resolves match/tag decisions.
4. System stages imports and user starts import.
5. Worker processes queued imports and marks completed/failed.

### 4.2 Alternative Flows

1. User calls AI endpoints for mapping/normalization/reconciliation/tag suggestions before finalizing decisions.
2. Merge-group imports inherit tags from best-tagged sibling in group.

### 4.3 Error Scenarios

- Invalid JSON or missing required input arrays.
- Invalid import type.
- Import row skipped: not editable, no tags, no budget tag.
- Duplicate reference already exists in active payments.
- Processing timeout recovers stuck `processing` rows to `failed`.

## 5. Functional Requirements

- The system must parse/validate CSV rows into normalized payment structures.
- The system must stage imports with strategy and match metadata.
- The user can submit selected tags before queueing import.
- The system must process queued imports asynchronously.

## 6. Business Rules

- `ImportedPayment` statuses: pending, queued, processing, completed, failed.
- Editable statuses: pending/failed only.
- Unique reference per user in imported table.
- Budget tag is mandatory to enqueue import for execution.
- AI suggestion usage capped by global/request/user-day limits.
- Merge strategy updates existing matched payment/invoice; new strategy creates invoice and generated payments.

## 7. Data Model (Business View)

- `ImportedPayment`: raw transaction snapshot + strategy/match state + AI metadata + tags.
- `Payment` and `Invoice`: final financial records created/updated from import pipeline.
- `Tag`/`Budget`: mandatory categorization gate for import processing.

## 8. Interfaces

- APIs:
  - `/financial/payment/csv-mapping/`
  - `/financial/payment/process-csv/`
  - `/financial/payment/csv-resolve-imports/`
  - `/financial/payment/csv-import/`
  - `/financial/payment/csv-ai-map|csv-ai-normalize|csv-ai-reconcile/`
  - `/financial/payment/ai-tag-suggestions/`
- Background command: `python manage.py process_imported_payments`

## 9. Dependencies

- Depends on AI prompt/orchestration layer.
- Depends on invoice generation and validation utilities.
- Depends on budget-tag taxonomy.

## 10. Limitations / Gaps

- Split strategy exists as enum but processing path is effectively merge/new behavior.
- Import worker is command-driven, so operations depend on scheduler discipline.
- Some heuristics are locale-specific and may misclassify unusual CSV formats.

## 11. Opportunities

- Add explicit split-processing implementation.
- Add dry-run import simulation with expected ledger impact.
- Add per-user import dashboard (queued/failed/completed reasons).

## 12. Acceptance Criteria

- Given valid CSV rows, when processing upload, then each row returns mapped data and validation/match result.
- Given staged import items without budget tags, when starting import, then those items are skipped with reason.
- Given queued imports, when worker runs, then imports are converted to completed or failed with status description.

## 13. Assumptions

- Background worker is scheduled frequently enough for operational SLAs.
- Users review AI suggestions before final import confirmation.
