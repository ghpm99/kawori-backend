## 1. Feature Overview

* Name: Pusher Webhook & Channel Auth
* Summary: Receives Pusher webhooks, updates remote status/screen config, and authenticates private channel subscriptions.
* Purpose: Bridge backend state/events with real-time channel lifecycle.
* Business value: Keeps remote-control/event channels synchronized and authorized.

## 2. Current Implementation

* How it works today: `/pusher/webhook` validates signed webhook and dispatches event handlers; `/pusher/auth` returns channel auth payload for admin users.
* Main flows: webhook event validation -> event-specific handler (`occupied`, `vacated`, `client_event`); auth endpoint parses form body and calls pusher authenticate.
* Entry points (routes, handlers, jobs): `POST /pusher/webhook`, `POST /pusher/auth`.
* Key files involved (list with paths):
  * `pusher_webhook/views.py`
  * `pusher_webhook/application/use_cases/*.py`
  * `lib/pusher/__init__.py`

## 3. Architecture & Design

* Layers involved (frontend/backend): view -> use case -> pusher gateway.
* Data flow (step-by-step): incoming signed webhook -> validation -> iterate events -> update DB or emit channel status events.
* External integrations: Pusher SDK and webhook signature verification.
* State management (if applicable): screen config updates stored in `remote.Config`.

## 4. Data Model

* Entities involved: `Config` from remote app.
* Database tables / schemas: remote config table.
* Relationships: none.
* Important fields: config type and JSON value for screen dimensions.

## 5. Business Rules

* Explicit rules implemented in code: invalid webhook signature returns 400; auth endpoint requires admin group.
* Edge cases handled: channel event routing based on known event/channel names.
* Validation logic: auth request parsing is manual (`split('&')`) without strict decoding.

## 6. User Flows

* Normal flow: client subscribes to private channel -> backend auths; pusher lifecycle events drive occupancy updates.
* Error flow: bad signature -> `Webhook incorreto`.
* Edge cases: unknown events are ignored.

## 7. API / Interfaces

* Endpoints: `POST /pusher/webhook`, `POST /pusher/auth`.
* Input/output: webhook raw body/headers; auth form-like payload with `socket_id` and `channel_name`.
* Contracts: output for auth is pusher auth JSON.
* Internal interfaces: `lib.pusher.webhook` and `lib.pusher.auth` as core gateway functions.

## 8. Problems & Limitations

* Technical debt: manual form parsing in auth use case.
* Bugs or inconsistencies: lack of URL decoding/robust parser for auth body fields.
* Performance issues: none significant.
* Missing validations: no strict allowlist for channel names on auth endpoint.

## 9. Security Concerns ⚠️

* Any suspicious behavior: auth endpoint trusts parsed channel name directly.
* External code execution: none.
* Unsafe patterns: simplistic request body parsing can mishandle encoded values.
* Injection risks: channel names should be allowlisted to prevent unintended subscriptions.
* Hardcoded secrets: none in app code; pusher secret from env.
* Unsafe file/system access: none.

## 10. Improvement Opportunities

* Refactors: parse auth payload via Django `QueryDict` instead of manual split.
* Architecture improvements: explicit channel policy layer and per-user authorization checks.
* Scalability: central event handler registry for webhook event types.
* UX improvements: richer error messages for auth failures.

## 11. Acceptance Criteria

* Functional: signed webhook events are processed; admin can authenticate private channels.
* Technical: invalid signatures are rejected.
* Edge cases: malformed auth body returns safe failure.

## 12. Open Questions

* Unknown behaviors: required channel naming conventions are not documented.
* Missing clarity in code: expected pusher event schema changes over time.
* Assumptions made: pusher webhook signature validation stays compatible with SDK.
