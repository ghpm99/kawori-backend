# Changelog

## v5.0.0 - 2026-03-20

### Breaking Changes
- docs: Revamp README with detailed project overview and structure (0cd73ae)
- build(ci): introduce main to develop sync workflow (69b45ac)

### Features
- feat(mailer): add EmailQueue and UserEmailPreference models (3969426)
- feat(mailer): add email enqueue utilities (3a9ab0d)
- feat(mailer): add process_email_queue worker command with preference checks (76451fe)
- feat(mailer): add cleanup_email_queue command (864da6d)
- feat(mailer): add email preferences endpoint (50bcc9e)
- feat(ai): Implement multi-provider AI orchestration layer (ccbb51f)
- feat(ai): Introduce AI assistant for various features (0e47f3c)
- feat(ai): Implement financial AI features and endpoints (f15f844)
- feat(ai): Implement dynamic prompt management and override system (5f4d06b)
- feat(ai): Introduce telemetry, caching, and budget for AI executions (5594554)
- feat(ai): Implement AI execution metrics endpoints (2b269c0)

### Fixes
- fix(payment): Update payment model field defaults and statement ordering (05c0d36)
- fix: process_email_queue (a5a1229)
- fix: import csv flow (adb2c4e)
- fix(decimal): Use Decimal for Coalesce default values (459e0a1)
- fix: quality gates (f7f9b75)
- fix(release): avoid sync conflicts with ours merge strategy (11b2417)

### Maintenance
- docs: Revamp README with detailed project overview and structure (0cd73ae)
- refactor(email): Switch to Django EmailMessage for sending emails (7a62f90)
- test(mailer): add tests for email queue system (51eb0ad)
- refactor(auth): use email queue for password reset and verification (14d6b48)
- refactor(financial): use email queue for payment notifications (50ed03b)
- build(deps): bump pyjwt from 2.10.1 to 2.12.0 (ec1feb7)
- build(ci): introduce main to develop sync workflow (69b45ac)
- docs(ai): Add AI opportunities analysis document (717ba55)

## v4.0.0 - 2026-03-13

### Breaking Changes
- docs: Revamp README with detailed project overview and structure (0cd73ae)

### Features
- feat(mailer): add EmailQueue and UserEmailPreference models (3969426)
- feat(mailer): add email enqueue utilities (3a9ab0d)
- feat(mailer): add process_email_queue worker command with preference checks (76451fe)
- feat(mailer): add cleanup_email_queue command (864da6d)
- feat(mailer): add email preferences endpoint (50bcc9e)

### Fixes
- fix(payment): Update payment model field defaults and statement ordering (05c0d36)
- fix: process_email_queue (a5a1229)

### Maintenance
- docs: Revamp README with detailed project overview and structure (0cd73ae)
- refactor(email): Switch to Django EmailMessage for sending emails (7a62f90)
- test(mailer): add tests for email queue system (51eb0ad)
- refactor(auth): use email queue for password reset and verification (14d6b48)
- refactor(financial): use email queue for payment notifications (50ed03b)

## v3.0.0 - 2026-03-12

### Breaking Changes
- docs: Revamp README with detailed project overview and structure (0cd73ae)

### Maintenance
- docs: Revamp README with detailed project overview and structure (0cd73ae)

## v2.1.0 - 2026-03-11

### Features
- feat: implements transactional integrity for all operations (c2d924e)
- feat(audit): track and execute registered release scripts (36f0857)

### Fixes
- fix: testes (48bedf5)
- fix: pipeline (c25b9ae)
- fix: security vulnerability (8e21da3)
- fix: recalculate invoices (1a5e7f9)
- fix(financial): align report summary endpoint contract (73f19bd)
- fix(financial): align report count endpoint contract (9995240)
- fix(financial): align report amount endpoint contract (1b11671)
- fix(financial): align report open amount endpoint contract (4c576f4)
- fix(financial): align report closed amount endpoint contract (d91a39e)
- fix(financial): align report metrics endpoint contract (0b88b64)
- fix(payment): align monthly report endpoint contract (b50badd)
- fix(financial): align report tag breakdown endpoint contract (bf660d9)
- fix(financial): align report forecast endpoint contract (08a0b94)
- fix: report_forecast_amount_value view (b0dc0d4)
- fix(release): handle commits without body in prepare script (0715392)
- fix(release): harden release pr automation (1494d55)
- fix(release): keep release pr branch in sync (955fcc7)

### Maintenance
- docs(release): define automation and one-off workflow rules (366280d)
- build(release): automate versioning and publication (23677bd)
- docs(release): align workflow documentation with automation (66cebf7)

## v2.0.2 - 2026-03-11

### Maintenance
- Historical baseline before automated release preparation was introduced.
