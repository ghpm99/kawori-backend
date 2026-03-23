## 1. Feature Overview

- Name: Invoice Management
- Summary: Creates and manages invoices, installment plans, and invoice-tag/payment links.
- Target user: Financial users.
- Business value: Centralizes payable/receivable obligations with installment control.

## 2. Problem Statement

- Users need invoice-level tracking of total/open/closed amounts and tags.
- Without this, payment tracking is fragmented and reporting loses context.

## 3. Current Behavior

- List/filter active invoices by status/type/dates/name/installments.
- Retrieve invoice details and invoice payments.
- Create invoice with required fields and optional tags.
- Auto-generate installment payments from invoice data.
- Update invoice fields (`name`, `date`, `active`, `tags`).
- Replace invoice tags in bulk.

## 4. User Flows

### 4.1 Main Flow

1. User submits invoice data.
2. System validates required fields and type.
3. System saves invoice, attaches tags, generates installment payments.

### 4.2 Alternative Flows

1. User edits invoice details.
2. User views linked payments with filters.

### 4.3 Error Scenarios

- Missing required fields.
- Invalid type not `credit`/`debit` mapping.
- Tag IDs not owned by user.
- Invoice not found.

## 5. Functional Requirements

- The system must create invoices and installment payments.
- The user can list and filter invoices and linked payments.
- The system must allow tag updates with ownership checks.

## 6. Business Rules

- Invoice starts as open with `value_open = value`.
- Invoice has validation statuses (valid, value mismatch, empty payment date, missing budget tag, no payments).
- Budget-aware tag rendering uses `#` prefix for budget tags.

## 7. Data Model (Business View)

- `Invoice`: type, status, installments, value totals, next payment date, fixed flag, active flag.
- `Tag`: many-to-many with invoice.
- `Payment`: child installments of invoice.

## 8. Interfaces

- APIs:
  - `/financial/invoice/`
  - `/financial/invoice/new/`
  - `/financial/invoice/<id>/`
  - `/financial/invoice/<id>/save/`
  - `/financial/invoice/<id>/payments/`
  - `/financial/invoice/<id>/tags`

## 9. Dependencies

- Depends on payment generation utility.
- Depends on tag and budget relationship for categorization behavior.

## 10. Limitations / Gaps

- Update flow does not expose installment/amount restructuring logic.
- In some branches, HTTP status semantics are inconsistent.

## 11. Opportunities

- Add invoice-level recalculation endpoint with dry-run diagnostics.
- Add explicit duplicate detection for recurring invoices.

## 12. Acceptance Criteria

- Given valid invoice payload, when creating invoice, then invoice and installments are created.
- Given invoice ID, when requesting details, then totals and tags are returned.
- Given unauthorized tag IDs, when saving tags, then request fails with ownership error.

## 13. Assumptions

- Payment creation is the authoritative source for installment-level values.
