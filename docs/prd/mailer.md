## 1. Feature Overview

* Name: Mailer & Email Preferences
* Summary: Email queueing, notification copy assistance, user email preference management, and background queue processing/cleanup commands.
* Purpose: Decouple email generation from send delivery and enforce opt-out preferences.
* Business value: Reliable transactional/notification email delivery with retry and governance controls.

## 2. Current Implementation

* How it works today: app creates `EmailQueue` rows (`mailer/utils.py`), user preferences are managed via API, and management commands process pending queue items.
* Main flows: enqueue email -> worker sends/skips/fails with retries -> cleanup removes aged processed rows.
* Entry points (routes, handlers, jobs): `GET|PUT /mailer/preferences/`, `manage.py process_email_queue`, `manage.py cleanup_email_queue`.
* Key files involved (list with paths):
  * `mailer/models.py`
  * `mailer/utils.py`
  * `mailer/views.py`
  * `mailer/application/use_cases/email_preferences.py`
  * `mailer/management/commands/process_email_queue.py`
  * `mailer/management/commands/cleanup_email_queue.py`
  * `mailer/ai_assist.py`

## 3. Architecture & Design

* Layers involved (frontend/backend): API for preferences + queue producer utilities + command-based worker.
* Data flow (step-by-step): feature modules call enqueue helpers -> queued row persisted -> worker locks rows and sends via `EmailMessage` -> status transitions.
* External integrations: SMTP backend and optional AI prompt-driven copy generation.
* State management (if applicable): queue statuses `pending/sending/sent/failed/cancelled/skipped` with retry count and error capture.

## 4. Data Model

* Entities involved: `EmailQueue`, `UserEmailPreference`, `User`.
* Database tables / schemas: `mailer_email_queue`, `mailer_user_email_preference`.
* Relationships: email queue optionally linked to user; one preference row per user.
* Important fields: category/type/priority/status/scheduled_at/max_retries/retry_count/context_data.

## 5. Business Rules

* Explicit rules implemented in code: non-transactional emails can be skipped by user preferences; global mail send can be disabled via `MAILER_GLOBAL_ENABLED`; retries bounded by `max_retries`.
* Edge cases handled: invalid JSON for preferences update; missing preference row auto-created.
* Validation logic: preference update serializer validates allowed fields and boolean values.

## 6. User Flows

* Normal flow: auth/password/payment modules enqueue messages; worker sends and marks `sent`.
* Error flow: SMTP/send exception sets status `failed` and increments retry count.
* Edge cases: duplicate payment notification copy can be reused via dedupe key in last 24h.

## 7. API / Interfaces

* Endpoints: `GET /mailer/preferences/`, `PUT /mailer/preferences/`.
* Input/output: JSON preference payload with flags `allow_all_emails`, `allow_notification`, `allow_promotional`.
* Contracts: queue producer helpers for password reset, email verification, payment notifications.
* Internal interfaces: worker command uses transactional row locking (`select_for_update(skip_locked=True)`).

## 8. Problems & Limitations

* Technical debt: continuous worker loop has simple sleep polling; no robust distributed worker framework.
* Bugs or inconsistencies: failed sends reuse in-memory object after transaction boundary.
* Performance issues: per-email processing and render at enqueue time can be heavy for spikes.
* Missing validations: queue payload/body_html size limits not explicitly enforced.

## 9. Security Concerns ⚠️

* Any suspicious behavior: email content may include AI-generated text and user financial metadata.
* External code execution: none.
* Unsafe patterns: queue command prints email addresses/errors in logs; sensitive logging policy should be reviewed.
* Injection risks: HTML body templating must trust sanitized context sources.
* Hardcoded secrets: SMTP credentials are env-based.
* Unsafe file/system access: none.

## 10. Improvement Opportunities

* Refactors: migrate worker to Celery/RQ for better retry and observability.
* Architecture improvements: add dead-letter queue and explicit retry backoff policy.
* Scalability: batch send + parallel workers with idempotent job keys.
* UX improvements: self-service unsubscribe center by email category.

## 11. Acceptance Criteria

* Functional: emails can be queued, processed, retried, and cleaned up; preferences API works.
* Technical: opt-out logic is enforced for notification/promotional categories.
* Edge cases: global-disable setting causes `skipped` status instead of send attempt.

## 12. Open Questions

* Unknown behaviors: worker deployment mode (singleton vs multi-instance) is not documented.
* Missing clarity in code: retention/compliance requirements for stored email body data.
* Assumptions made: background command is scheduled/managed by infrastructure.
