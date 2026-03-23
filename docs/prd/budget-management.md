## 1. Feature Overview

* Name: Budget Management
* Summary: Budget allocation percentages by tag, default budget bootstrap, reset-to-default, and AI scenario suggestions.
* Purpose: Plan spending distribution and compare estimated vs actual expenses.
* Business value: Supports proactive financial planning and variance control.

## 2. Current Implementation

* How it works today: `budget/views.py` exposes list/save/reset/AI endpoints; service creates default tags+budgets.
* Main flows: read budget status for period; update percentages; reset to defaults; generate AI scenario recommendations.
* Entry points (routes, handlers, jobs): `/financial/budget/`, `/financial/budget/save`, `/financial/budget/reset`, `/financial/budget/ai-allocation-suggestions`.
* Key files involved (list with paths):
  * `budget/views.py`
  * `budget/models.py`
  * `budget/services.py`
  * `budget/ai_features.py`
  * `budget/application/use_cases/*.py`

## 3. Architecture & Design

* Layers involved (frontend/backend): view -> use case -> ORM + domain calculations.
* Data flow (step-by-step): period parsed -> income and debit totals queried from `Payment` -> per-budget estimated/actual values computed -> optional AI-like scenario generation from historical spending.
* External integrations: none (AI suggestions here are deterministic heuristics, not external LLM).
* State management (if applicable): budget percentages persisted on `Budget` rows linked one-to-one to tags.

## 4. Data Model

* Entities involved: `Budget`, `Tag`, `Payment`, `User`.
* Database tables / schemas: `financial_budget`, `financial_tag`, `financial_payment`.
* Relationships: budget belongs to user and one tag.
* Important fields: `allocation_percentage` with 0-100 validators.

## 5. Business Rules

* Explicit rules implemented in code: exclude `Entradas` tag from budget list; fallback earned-total uses recent fixed credits if current period has no earnings; reset uses predefined `DEFAULT_BUDGETS`.
* Edge cases handled: invalid period string falls back to current month to date.
* Validation logic: model validators enforce percentage bounds.

## 6. User Flows

* Normal flow: user loads budget panel -> sees allocation vs actual -> edits and saves percentages.
* Error flow: malformed request JSON handled as view-level failure; missing rows are skipped in batch update.
* Edge cases: users without budgets can receive defaults via onboarding/one-off command.

## 7. API / Interfaces

* Endpoints:
  * `GET /financial/budget/`
  * `POST /financial/budget/save`
  * `GET /financial/budget/reset`
  * `GET /financial/budget/ai-allocation-suggestions`
* Input/output: period query (`MM/YYYY`) and JSON list for updates.
* Contracts: save endpoint expects `{data:[{id,allocation_percentage}]}`.
* Internal interfaces: `create_default_budgets_for_user` is reused by auth signup/social onboarding.

## 8. Problems & Limitations

* Technical debt: service logs errors via `print` instead of structured logger.
* Bugs or inconsistencies: `Tag.get_or_create` pattern with annotated `trimmed_name` is non-standard and can be brittle.
* Performance issues: repeated per-user initialization loops in one-off scripts.
* Missing validations: save use case does not enforce total allocation sum rules.

## 9. Security Concerns ⚠️

* Any suspicious behavior: none critical.
* External code execution: none.
* Unsafe patterns: noisy exception handling in bootstrap service may hide failures.
* Injection risks: low.
* Hardcoded secrets: none.
* Unsafe file/system access: none.

## 10. Improvement Opportunities

* Refactors: enforce domain rule for allocation total (e.g., exactly 100%).
* Architecture improvements: event-driven recomputation cache for budget insights.
* Scalability: bulk update optimizations and fewer per-budget queries.
* UX improvements: suggest diffs before applying reset/scenario allocations.

## 11. Acceptance Criteria

* Functional: budgets can be listed, updated, reset, and suggested.
* Technical: percentages remain within validator bounds and link to user-owned tags.
* Edge cases: empty earnings period still returns estimated baseline using fixed income fallback.

## 12. Open Questions

* Unknown behaviors: required policy for total allocation (100% vs flexible) is undefined.
* Missing clarity in code: expected behavior when default tags are renamed by user.
* Assumptions made: budget tag naming conventions remain stable.
