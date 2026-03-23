## 1. Feature Overview

- Name: Financial Reporting & Metrics
- Summary: Provides summary reports, totals, tag distribution, projection, overdue health, daily cash flow, top expenses, and AI-generated insights.
- Target user: Financial users.
- Business value: Supports decision-making with aggregated financial intelligence.

## 2. Problem Statement

- Users need consolidated financial insights across periods and categories.
- Without this, planning and monitoring rely on raw transactional views.

## 3. Current Behavior

- Exposes period-based metrics endpoints (count, amount total/open/closed, invoice by tag, forecast).
- Provides payment summary report backed by materialized/report table `financial_paymentsummary`.
- Computes growth/revenue/expense/profit metrics with period-over-period comparison.
- Provides daily cash flow and projected monthly balances with risk levels.
- Provides overdue health for open debit payments and top critical categories.
- Provides tag evolution vs previous period.
- Optional AI financial insights endpoint receives validated payload.

## 4. User Flows

### 4.1 Main Flow

1. User selects date period.
2. User requests report endpoint.
3. System returns aggregated data series and summary.

### 4.2 Alternative Flows

1. User requests AI insights for selected payload.
2. User requests projection months ahead from chosen start date.

### 4.3 Error Scenarios

- Missing required date range on strict endpoints.
- `date_from > date_to` rejected.

## 5. Functional Requirements

- The system must return summarized financial metrics for selected periods.
- The user can fetch category and trend-focused reports.
- The system should provide AI insights payload when available.

## 6. Business Rules

- Most reports scope by authenticated user and active payments/invoices.
- Top expenses use debit payments only.
- Overdue health uses debit + open + payment_date before current date.
- Projection risk: negative balance = high, low margin ratio = medium, else low.

## 7. Data Model (Business View)

- Source entities: `Payment`, `Invoice`, `Tag`, `Contract`.
- Derived/report entity: `financial_paymentsummary` (queried by SQL).

## 8. Interfaces

- APIs under `/financial/report/`:
  - root summary, `metrics/`, `ai-insights/`, `count_payment`, `amount_payment`, `amount_payment_open`, `amount_payment_closed`, `amount_invoice_by_tag`, `amount_forecast_value`, `daily_cash_flow`, `top_expenses`, `balance_projection`, `overdue_health`, `tag_evolution`.

## 9. Dependencies

- Depends on payment/invoice consistency.
- Depends on report table/materialization strategy for summary endpoint.
- AI insights depends on AI module feature flags and providers.

## 10. Limitations / Gaps

- Mixed ORM and raw SQL increases maintenance complexity.
- Some legacy reporting functions remain in `financial/views.py` beyond routed endpoints.

## 11. Opportunities

- Standardize report computation on one query strategy.
- Add saved report presets and benchmark targets.

## 12. Acceptance Criteria

- Given valid period, when calling `amount_payment`, then total amount for active payments is returned.
- Given valid period, when calling `top_expenses`, then top debit expenses sorted by amount are returned.
- Given invalid period ordering, when calling required-period endpoints, then request is rejected with validation message.

## 13. Assumptions

- Data freshness for materialized/report sources is handled operationally.
