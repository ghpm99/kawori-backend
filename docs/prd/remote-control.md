## 1. Feature Overview

* Name: Remote Control
* Summary: Admin-only endpoints to send remote display commands (keyboard/mouse/hotkey/command), manage screen-size config, and receive screenshot uploads.
* Purpose: Operate a remote client through real-time Pusher events.
* Business value: Enables operator tooling/automation for remote sessions.

## 2. Current Implementation

* How it works today: `remote/views.py` validates admin user and forwards commands to `lib.pusher` helpers via use cases.
* Main flows: send input event; retrieve screen-size config; upload screenshot and notify subscribers.
* Entry points (routes, handlers, jobs): `/remote/send-command`, `/remote/hotkey`, `/remote/key-press`, `/remote/mouse-*`, `/remote/save-screenshot`, `/remote/screen-size`.
* Key files involved (list with paths):
  * `remote/views.py`
  * `remote/application/use_cases/*.py`
  * `remote/models.py`
  * `lib/pusher/__init__.py`

## 3. Architecture & Design

* Layers involved (frontend/backend): API -> use-case wrapper -> pusher event gateway.
* Data flow (step-by-step): admin request -> serializer/use-case -> pusher trigger -> remote client consumes event.
* External integrations: Pusher channels/events.
* State management (if applicable): `Config` table stores screen size JSON; `Screenshot` table stores latest image file.

## 4. Data Model

* Entities involved: `Config`, `Screenshot`.
* Database tables / schemas: remote config/screenshot tables.
* Relationships: none complex.
* Important fields: config type/value and screenshot image path.

## 5. Business Rules

* Explicit rules implemented in code: access requires admin group; screenshot endpoint replaces fixed filename `screenshot.png`; keyboard key list endpoint returns static allowed keys.
* Edge cases handled: missing image upload returns 400.
* Validation logic: basic serializer validation for command payloads.

## 6. User Flows

* Normal flow: admin sends remote event -> remote client executes action.
* Error flow: invalid auth/payload -> 4xx response.
* Edge cases: save screenshot updates or creates row id 1 and notifies via pusher.

## 7. API / Interfaces

* Endpoints: command/hotkey/key/mouse/screenshot/keyboard-keys/screen-size endpoints under `/remote/`.
* Input/output: JSON for commands, multipart for screenshot upload, JSON for key catalog.
* Contracts: pusher payload keys (`cmd`, `hotkey`, `keys`, `x`, `y`, `button`, `value`).
* Internal interfaces: use cases are mostly thin wrappers around `lib.pusher` function calls.

## 8. Problems & Limitations

* Technical debt: minimal payload-level validation and no command authorization granularity.
* Bugs or inconsistencies: keyboard key endpoint hardcodes large static list in view.
* Performance issues: screenshot overwrite strategy does not keep history.
* Missing validations: no content-type/size checks for uploaded screenshots.

## 9. Security Concerns ⚠️

* Any suspicious behavior: remote command endpoint can issue arbitrary command strings to connected client via pusher.
* External code execution: indirect remote execution risk (depends on remote client behavior).
* Unsafe patterns: fixed shared channels (`private-display`) with broad command semantics.
* Injection risks: if downstream client executes commands unsafely, this API is a high-risk control plane.
* Hardcoded secrets: none in module, but pusher credentials required.
* Unsafe file/system access: uploaded screenshot written to predictable path and prior file removed.

## 10. Improvement Opportunities

* Refactors: enforce structured command schema with allowlist.
* Architecture improvements: RBAC per remote action and signed command intents.
* Scalability: store screenshot history with retention instead of single-file overwrite.
* UX improvements: command acknowledgment and execution status feedback loop.

## 11. Acceptance Criteria

* Functional: admin can send all supported remote interactions and upload screenshot.
* Technical: unauthorized users are blocked; pusher events are emitted on successful requests.
* Edge cases: missing image/payload returns clear errors.

## 12. Open Questions

* Unknown behaviors: exact remote client trust boundary and command interpreter are outside this repo.
* Missing clarity in code: no explicit audit of payload shape beyond decorators.
* Assumptions made: pusher private channel auth is correctly enforced upstream.
