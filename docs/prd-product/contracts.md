## 1. Feature Overview

- Name: Contract Management
- Summary: Manages financial contracts and links invoices under each contract.
- Target user: Financial users.
- Business value: Organizes liabilities/agreements and aggregates open/closed values.

## 2. Problem Statement

- Financial entries need grouping at contract level for tracking totals.
- Without this, users lose contract-level visibility and consolidation.

## 3. Current Behavior

- Create contract with name.
- List/filter contracts with pagination.
- View contract details and related invoices.
- Add invoice directly under contract.
- Merge contracts by moving invoices to a target contract.
- Recalculate all contract values from invoice/payment state.

## 4. User Flows

### 4.1 Main Flow

1. User creates contract.
2. User adds invoice to contract.
3. System generates payments for invoice and updates contract totals.

### 4.2 Alternative Flows

1. User merges multiple contracts into one target contract.
2. System reassigns invoices and deletes merged contracts.

### 4.3 Error Scenarios

- Contract not found.
- Provided tags in invoice creation do not belong to user.

## 5. Functional Requirements

- The system must create and list user-scoped contracts.
- The user can retrieve invoices per contract.
- The system must support contract merge and value recalculation.

## 6. Business Rules

- Contract totals are derived from active invoices/payments (`value`, `value_open`, `value_closed`).
- Contract merge skips target contract ID if passed in merge list.
- User ownership is enforced on all operations.

## 7. Data Model (Business View)

- `Contract`: name and aggregated values.
- `Invoice`: optional foreign key to contract.
- `Payment`: indirectly impacts contract through invoice totals.

## 8. Interfaces

- APIs:
  - `/financial/contract/`
  - `/financial/contract/new`
  - `/financial/contract/<id>/`
  - `/financial/contract/<id>/invoices/`
  - `/financial/contract/<id>/invoice/`
  - `/financial/contract/<id>/merge/`
  - `/financial/contract/update_all_contracts_value`

## 9. Dependencies

- Depends on invoice generation and payment generation utilities.
- Depends on tag ownership checks when creating contract invoices.

## 10. Limitations / Gaps

- No explicit contract close/archive lifecycle.
- Minimal validation on contract name format.

## 11. Opportunities

- Add contract status and timeline.
- Add merge preview (impact on totals) before execution.

## 12. Acceptance Criteria

- Given valid financial user, when creating a contract, then contract is persisted with zeroed totals.
- Given valid contract and invoice payload, when invoice is added, then payments are generated and contract totals increase.
- Given merge list, when merging contracts, then invoices move to target and source contracts are removed.

## 13. Assumptions

- Contract totals are intentionally recomputed from invoice/payment data, not treated as source-of-truth input.
