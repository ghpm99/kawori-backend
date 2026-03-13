# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Mandatory workflow rules

- Every commit that may reach `develop` or `main` must follow Conventional Commits.
- Every change that requires a one-off script, data backfill, recalculation, or operational action must register that action in `scripts.xml` and document it in `docs/oneoff-registry.md`.
- Treat `docs/engineering-rules.md`, `docs/release-deploy-plan.md`, and `docs/oneoff-registry.md` as the operational source of truth.
- Do not change the workflow without updating the corresponding file in `docs/` in the same change set.

## Commands

All commands require `--settings=kawori.settings.development`:

```bash
# Run development server
python manage.py runserver --settings=kawori.settings.development

# Run all tests
python manage.py test --settings=kawori.settings.development

# Run tests for a specific app
python manage.py test payment --settings=kawori.settings.development

# Run a single test class or method
python manage.py test payment.tests.views.test_get_all_view.GetAllViewTestCase --settings=kawori.settings.development
python manage.py test payment.tests.views.test_get_all_view.GetAllViewTestCase.test_get_all_view_success_without_filters --settings=kawori.settings.development

# Migrations
python manage.py makemigrations --settings=kawori.settings.development
python manage.py migrate --settings=kawori.settings.development

# Email cron job
python manage.py cron_payment_email --settings=kawori.settings.development
```

Environment variables are loaded via `.env` at the project root (uses `python-dotenv`). Required vars: `SECRET_KEY`. Optional: `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `NOTIFICATION_EMAIL`.

## Architecture

Django 4.2 REST API using **function-based views** (not class-based), **JWT via HttpOnly cookies** (not Authorization headers), and **PostgreSQL**.

### Settings hierarchy
- `kawori/settings/base.py` — shared config (installed apps, middleware, JWT, email backend)
- `kawori/settings/development.py` — imports base, loads `.env`, sets `DEBUG=True`, PostgreSQL DB named `kawori`
- `kawori/settings/production.py` — production overrides
- `kawori/settings/local_settings.py` — optional local overrides (gitignored), imported at end of development.py

### Authentication pattern
JWT tokens are stored in **HttpOnly cookies**, not Authorization headers. The custom decorator `kawori/decorators.py::validate_user(group)` reads the `access_token` cookie, verifies it, and injects the `user` object into the view. All protected views use `@validate_user("group_name")` — the main group for financial features is `"financial"`.

### URL structure
```
/auth/          → authentication (login, logout, signup, token refresh, CSRF)
/financial/     → contract/, invoice/, payment/, tag/, report/, earnings/, budget/
/discord/       → discord integration
/facetexture/   → Black Desert Online class/character images
/classification/ → classification features
/profile/       → user profile
/analytics/     → analytics
/remote/        → remote control
/pusher/        → Pusher webhook
```

### Financial domain model
The core financial hierarchy is: **Contract → Invoice → Payment**

- `Contract` (financial_contract): groups invoices, tracks aggregate value/value_open/value_closed
- `Invoice` (financial_invoice): a bill with installments. Has M2M `tags`. Tracks value_open/value_closed. When `fixed=True` and a payment is paid off, a new invoice for next month is auto-created.
- `Payment` (financial_payment): individual payment installment belonging to an invoice
- `Tag` (financial_tag): user-owned labels attached to invoices
- `Budget` (financial_budget): one-to-one with Tag, defines allocation_percentage. Tags with a Budget are "budget tags" and get special treatment (prefixed with `#` in API responses)

`financial/utils.py` contains shared logic: `generate_payments(invoice)` creates Payment records from an Invoice, `calculate_installments(value, n)` splits amounts across installments (last one absorbs rounding).

### CORS & CSRF
Custom middleware in `kawori/middleware.py`:
- `CsrfCookieOnlyMiddleware`: reads CSRF token from cookie (not header) — frontend must include cookie
- `SimpleCorsMiddleware`: allows origins in `BASE_URL_FRONTEND_LIST` (dev: localhost:3000 and localhost:5173)
- `OriginFilterMiddleware`: optional stricter origin filtering (not in default middleware stack)

### Testing pattern
Tests use Django's `TestCase` with `setUpTestData` (not `setUp`) for data creation. Authentication in tests works by POST-ing to `da_token_obtain_pair` and storing response cookies. Test structure for `payment` app uses subdirectory `tests/views/` with each view in its own file, imported into `tests/test_views.py`.

### BDO (Black Desert Online) features
`kawori/utils.py` contains image processing utilities (PIL, numpy, scipy) for generating class icons with glow effects from sprite sheets. `facetexture` app handles class image/texture generation. These are unrelated to the financial features.

### lib/ directory
Contains integrations: `lib/google/` (Google Cloud Storage), `lib/pusher/` (Pusher real-time events).

IMPORTANT: Read and follow all instructions in AGENTS.md before starting any task.