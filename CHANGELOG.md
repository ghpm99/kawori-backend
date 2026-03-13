# Changelog

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
