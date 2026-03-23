## 1. Feature Overview

- Name: Earnings Tracking
- Summary: Provides filtered listing of credit payments as earnings view.
- Target user: Financial users.
- Business value: Separates income monitoring from expense management.

## 2. Problem Statement

- Users need a dedicated income lens.
- Without it, income analysis is mixed with all transactions.

## 3. Current Behavior

- Endpoint lists payments with `type=credit` by default.
- Supports additional filters (status, dates, installments, active/fixed, contract name).
- Returns contract metadata for each earning item.

## 4. User Flows

### 4.1 Main Flow

1. User opens earnings view.
2. System returns paginated credit payments.

### 4.2 Alternative Flows

1. User filters by status/date range.

### 4.3 Error Scenarios

- Invalid token/group permission blocks access.

## 5. Functional Requirements

- The system must list user earnings from credit payments.
- The user can apply standard payment filters.

## 6. Business Rules

- Earnings source is `Payment.TYPE_CREDIT`.
- User scope and financial role permission are mandatory.

## 7. Data Model (Business View)

- `Payment` (credit only in this feature).
- `Invoice` + `Contract` names included for context.

## 8. Interfaces

- API: `/financial/earnings/`.

## 9. Dependencies

- Depends on payment and contract linkage integrity.

## 10. Limitations / Gaps

- No dedicated earnings KPIs (only listing).

## 11. Opportunities

- Add recurring income insights and variance vs expected income.

## 12. Acceptance Criteria

- Given financial user, when requesting earnings endpoint, then paginated credit payments are returned.

## 13. Assumptions

- Income records are modeled as credit payments consistently.
