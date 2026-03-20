# Repository Guidelines

## Project Structure & Module Organization
This repository is a Django 4.2 backend with a modular, app-per-domain layout. Core project config lives in `kawori/` (URLs, middleware, ASGI/WSGI, and settings split across `kawori/settings/{base,development,production}.py`).
Business domains are top-level apps such as `payment/`, `financial/`, `authentication/`, `audit/`, and related modules, each typically containing `models.py`, `views.py`, `urls.py`, `migrations/`, and tests.
Templates and static-related assets are in `templates/` and `media/`. Shared utilities live in `lib/`.

## Build, Test, and Development Commands
- `python -m venv .venv` and `.venv\Scripts\activate` (Windows): create and activate the local environment.
- `pip install -r requirements.txt`: install backend dependencies.
- `make run`: start the local server with `kawori.settings.development`.
- `make makemigrations`: generate migration files for model changes.
- `make migrate`: apply database migrations.
- `make test`: run the Django test suite with development settings.
- `make ci`: run the same local quality gate validations used in GitHub Actions CI.
- `make build`: run `collectstatic --no-input` for deploy and static preparation.

## Delivery Gate
Running `make ci` is mandatory before finalizing any delivery.

## Coding Style & Naming Conventions
Use 4 spaces, UTF-8, LF endings, and max line length 130 (`.editorconfig`, `.flake8`).
Follow Django naming norms: `snake_case` for functions and variables, `PascalCase` for classes, and clear app-scoped module names such as `payment/tests/views/test_save_new_view.py`.
Keep views thin when possible and move reusable business logic into `utils.py` or dedicated service helpers.

## Testing Guidelines
Primary framework is Django's built-in test runner (`python manage.py test`).
Place tests either as `app/tests.py` or package-style under `app/tests/` with files named `test_*.py`.
Add or update tests for every behavior change, especially endpoints, serializers, and management commands. No explicit coverage threshold is configured.

## Commit, Release, and Pull Request Guidelines
Recent history follows Conventional Commit style and that convention is now mandatory for any commit that may reach `develop` or `main`.

Use:
- `feat(scope): ...`
- `fix(scope): ...`
- `refactor(scope): ...`
- `test(scope): ...`
- `docs(scope): ...`
- `build(scope): ...`
- `chore(scope): ...`

Use `!` or a `BREAKING CHANGE:` footer for backward-incompatible changes.

Operational rules:
- Conventional Commits are required because release automation will depend on commit history to infer semantic version bumps.
- For PRs, include concise summary, impacted apps or endpoints, migration notes, test evidence, and linked issue or task when available.

## One-Off Registration Policy
Any one-off script, backfill, recalculation, repair task, or operational step introduced by a change must be registered before merge.

Required actions:
- add the machine-readable entry to `scripts.xml`
- add the human-readable record to `docs/oneoff-registry.md`
- document execution expectations and idempotency

No change that depends on manual environment action is considered complete until the corresponding one-off is registered and documented.

## Workflow Source Of Truth
The release and deploy process is documented under `docs/` and those documents must be updated whenever the workflow changes:
- `docs/engineering-rules.md`
- `docs/release-deploy-plan.md`
- `docs/oneoff-registry.md`

## Security & Configuration Tips
Use `.env.example` as the template for local `.env` values. Never commit secrets such as email credentials, API keys, or production settings.
Validate settings changes across `development.py` and `production.py` before merge.
