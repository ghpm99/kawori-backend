## 1. Feature Overview

* Name: AI Platform & Telemetry
* Summary: Multi-provider LLM orchestration, prompt registry/overrides, task routing with fallback, response caching, budget guardrails, and execution metrics APIs.
* Purpose: Provide a reusable AI execution backbone for payment/audit/mailer/release features.
* Business value: Centralizes AI governance, cost control, observability, and provider flexibility.

## 2. Current Implementation

* How it works today: `ai.assist.safe_execute_ai_task` gates feature flags + provider presence + budget; `AIOrchestrator` routes tasks, retries/fallbacks, normalizes outputs, emits telemetry, and optionally persists execution events.
* Main flows: build prompt request -> resolve route/provider -> optional cache hit -> provider call -> strategy normalization -> telemetry emit -> consumer feature receives structured output.
* Entry points (routes, handlers, jobs): `/ai/metrics/overview|breakdown|timeseries|events` plus internal API used by payment/mailer/audit/release tooling.
* Key files involved (list with paths):
  * `ai/assist.py`, `ai/orchestrator.py`, `ai/utils.py`
  * `ai/prompt_service.py`, `ai/routing.py`, `ai/factory.py`
  * `ai/providers/*.py`
  * `ai/models.py`, `ai/telemetry.py`, `ai/budget.py`
  * `ai/views.py`, `ai/application/use_cases/*.py`

## 3. Architecture & Design

* Layers involved (frontend/backend): internal service layer + provider gateway layer + Django models/admin + metrics API layer.
* Data flow (step-by-step): feature builds prompt payload -> prompt service resolves file/DB override -> task routed by task type/feature -> provider request executed -> response normalized and traced -> cache + telemetry updates.
* External integrations: OpenAI, Anthropic, Google Gemini, Cohere, and OpenAI-compatible providers via HTTP.
* State management (if applicable): prompt overrides/history, execution event records, budget policies, in-memory/or local cache abstraction.

## 4. Data Model

* Entities involved: `PromptOverride`, `PromptOverrideHistory`, `AIExecutionEvent`, `AIBudgetPolicy`.
* Database tables / schemas: `ai_prompt_override`, `ai_prompt_override_history`, `ai_execution_event`, `ai_budget_policy`.
* Relationships: override/history/user relations; execution events optional user linkage.
* Important fields: prompt key/environment/version, active validity windows, task/provider/model tokens/cost/latency/success metadata.

## 5. Business Rules

* Explicit rules implemented in code: feature-level enable flags; active override cannot be edited in-place; budget policies can block execution by feature/user daily/monthly limits; routing may escalate to high-quality tier when confidence is low.
* Edge cases handled: provider misconfiguration, timeout, invalid response format, cache miss/hit/bypass tracking.
* Validation logic: prompt override `clean()` enforces task type/schema/token/version/validity and change reason for active entries.

## 6. User Flows

* Normal flow: internal feature requests AI output and receives structured response with trace metadata.
* Error flow: provider/request/format failures return `None` at safe wrapper level; execution telemetry records failure.
* Edge cases: no configured provider or disabled feature bypasses AI calls cleanly.

## 7. API / Interfaces

* Endpoints: `GET /ai/metrics/overview/`, `/breakdown/`, `/timeseries/`, `/events/`.
* Input/output: filterable metrics by period/feature/provider/model/task/success/user.
* Contracts: task request/response DTOs (`AITaskRequest`, `AITaskResponse`) and provider completion contracts.
* Internal interfaces: prompt keys defined in `ai/prompts/registry.yaml` and consumed via `build_ai_request_from_prompt`.

## 8. Problems & Limitations

* Technical debt: orchestrator is complex and highly configurable, increasing misconfiguration risk.
* Bugs or inconsistencies: cache hit response rewrites trace id; downstream systems must not treat trace id as immutable provider execution id.
* Performance issues: synchronous provider calls in request path for several features.
* Missing validations: provider-specific payload constraints are not centrally schema-validated beyond runtime exceptions.

## 9. Security Concerns ⚠️

* Any suspicious behavior: outbound requests to many configurable base URLs can exfiltrate data if env is misconfigured.
* External code execution: none direct, but extensive external network execution to AI vendors.
* Unsafe patterns: prompt override DB can alter production behavior; requires strict admin RBAC and audit.
* Injection risks: prompt template rendering must trust context assembly to avoid accidental sensitive leakage.
* Hardcoded secrets: none in code; API keys sourced from environment.
* Unsafe file/system access: prompt template/registry files loaded from configured paths.

## 10. Improvement Opportunities

* Refactors: isolate provider adapters behind stricter typed response schemas.
* Architecture improvements: async execution queue for non-blocking endpoints.
* Scalability: distributed cache and centralized telemetry pipeline.
* UX improvements: admin UI for prompt resolution stats and budget burn-down.

## 11. Acceptance Criteria

* Functional: AI tasks execute across configured providers with fallback and structured outputs.
* Technical: metrics endpoints expose filtered telemetry; budget gates block over-limit usage.
* Edge cases: timeout/configuration/format failures are captured without crashing caller feature.

## 12. Open Questions

* Unknown behaviors: formal SLA for provider fallback and retry policy per feature.
* Missing clarity in code: governance around non-admin access to prompt override admin is not in module code.
* Assumptions made: environment variables and provider credentials are correctly managed outside repository.
