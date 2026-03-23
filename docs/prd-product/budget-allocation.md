## 1. Feature Overview

- Name: Budget Allocation Management
- Summary: Maintains percentage allocation per budget tag, compares estimated vs actual expense, supports reset, and provides scenario suggestions.
- Target user: Financial users.
- Business value: Converts spending goals into enforceable category allocations.

## 2. Problem Statement

- Users need planned budget percentages tied to spending categories.
- Without this, category goals cannot be monitored against actual expenses.

## 3. Current Behavior

- Lists budgets by period with fields: allocation %, estimated expense, actual expense.
- Calculates total earned from credit payments in period; if zero, predicts from recent fixed credits.
- Excludes `Entradas` tag from budgeting output.
- Saves budget allocation percentage updates in bulk.
- Resets allocations to default percentages.
- AI suggestion endpoint returns conservative/base/aggressive scenarios from current + 6-month historical behavior.
- Default budgets/tags are auto-created for new users and social signups.

## 4. User Flows

### 4.1 Main Flow

1. User opens budget list for period.
2. System returns current allocation and actual spend per category.
3. User adjusts allocation and saves.

### 4.2 Alternative Flows

1. User requests AI allocation suggestions.
2. User resets allocations to defaults.

### 4.3 Error Scenarios

- Invalid period format falls back to current month behavior.

## 5. Functional Requirements

- The system must persist per-tag allocation percentages.
- The user can reset budgets to defaults.
- The system should provide scenario-based suggestions.

## 6. Business Rules

- `Budget` unique by `(user, tag)`.
- `allocation_percentage` constrained 0 to 100.
- Suggested base scenario blends current allocation (55%) and historical spend share (45%).
- Scenario multipliers adjust essential/discretionary tags.

## 7. Data Model (Business View)

- `Budget`: allocation percentage per user/tag.
- `Tag`: category anchor.
- `Payment`: source for earned (credit) and actual expense (debit) computation.

## 8. Interfaces

- APIs:
  - `/financial/budget/`
  - `/financial/budget/save`
  - `/financial/budget/reset`
  - `/financial/budget/ai-allocation-suggestions`

## 9. Dependencies

- Depends on tags and payment transactions.
- Depends on onboarding flow to seed default budgets.

## 10. Limitations / Gaps

- No explicit validation that total allocation sum equals 100 on save.

## 11. Opportunities

- Add budget overrun alerts and forecasted month-end variance.
- Add guided rebalancing recommendations after major spending changes.

## 12. Acceptance Criteria

- Given valid allocations payload, when saving budget, then percentages are updated.
- Given reset request, when executed, then user budgets match default template.
- Given period, when listing budgets, then estimated and actual expenses are returned per category.

## 13. Assumptions

- Budget tags are already associated to invoices for meaningful actual expense rollup.
