## 1. Feature Overview

- Name: Email Queue & Preferences
- Summary: Queues transactional/notification/promotional emails, processes queue in worker, and lets users control preference categories.
- Target user: End users and operations.
- Business value: Reliable asynchronous communication with user-level consent controls.

## 2. Problem Statement

- Immediate SMTP on request path is fragile and ignores preference controls.
- Without queue + preferences, communications fail silently or violate user opt-outs.

## 3. Current Behavior

- Email preference endpoint (`GET/PUT`) reads/updates per-user flags.
- Queue model stores payload, priority, status, retries, category, schedule.
- Worker command processes pending/failed queued records with retry and skip rules.
- Global flag `MAILER_GLOBAL_ENABLED` can skip all sends.
- Non-transactional categories honor user preference; transactional ignores opt-out.
- Cleanup command deletes old sent/cancelled/skipped emails.
- Financial payment notifications are enqueued by cron command using template + optional AI copy.

## 4. User Flows

### 4.1 Main Flow

1. System enqueues email event.
2. Worker picks eligible queue items.
3. Worker sends email and marks sent, or failed/skipped with reason.

### 4.2 Alternative Flows

1. User updates preferences to disable notification/promotional emails.
2. Subsequent matching emails are skipped.

### 4.3 Error Scenarios

- Invalid preference payload JSON.
- SMTP send failure increments retry and stores last error.
- Emails exceeding retry limit stop being picked.

## 5. Functional Requirements

- The system must support asynchronous email queue processing.
- The user can update email preference flags.
- The system should skip non-transactional emails when preferences disallow them.

## 6. Business Rules

- Status lifecycle: pending -> sending -> sent/failed/skipped/cancelled.
- Category logic: transactional bypasses preference blocks.
- Queue selection requires `scheduled_at <= now` and `retry_count < max_retries`.

## 7. Data Model (Business View)

- `EmailQueue`: recipient, template content, type/category, priority, retries, timestamps, status.
- `UserEmailPreference`: allow_all, allow_notification, allow_promotional.

## 8. Interfaces

- API: `/mailer/preferences/`.
- Commands:
  - `python manage.py process_email_queue`
  - `python manage.py cleanup_email_queue --days <N>`

## 9. Dependencies

- Depends on SMTP configuration.
- Used by authentication (reset/verify email), financial notifications, and AI prompt copy generation.

## 10. Limitations / Gaps

- No dead-letter queue for permanently failed emails.
- No native per-template analytics (open/click metrics).

## 11. Opportunities

- Add queue monitoring dashboard and alerting.
- Add deduplicated campaign/promotion tooling.

## 12. Acceptance Criteria

- Given a queued transactional email, when worker runs and SMTP succeeds, then status becomes sent.
- Given notification email and user disabled notifications, when worker runs, then status becomes skipped with reason.
- Given invalid preference payload, when updating preferences, then request is rejected.

## 13. Assumptions

- Worker is deployed as recurring job/long-running process in operations.
