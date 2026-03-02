# Repository Guidelines

## Project Structure & Module Organization
This repository is a Django 4.2 backend with a modular, app-per-domain layout. Core project config lives in `kawori/` (URLs, middleware, ASGI/WSGI, and settings split across `kawori/settings/{base,development,production}.py`).  
Business domains are top-level apps such as `payment/`, `financial/`, `authentication/`, `audit/`, etc., each typically containing `models.py`, `views.py`, `urls.py`, `migrations/`, and tests.  
Templates and static-related assets are in `templates/` and `media/`. Utility/shared code is in `lib/`.

## Build, Test, and Development Commands
- `python -m venv .venv` and `.venv\Scripts\activate` (Windows): create/activate local environment.
- `pip install -r requirements.txt`: install backend dependencies.
- `make run`: start local server with `kawori.settings.development`.
- `make makemigrations`: generate migration files for model changes.
- `make migrate`: apply database migrations.
- `make test`: run Django test suite with development settings.
- `make build`: run `collectstatic --no-input` for deploy/static prep.

## Coding Style & Naming Conventions
Use 4 spaces, UTF-8, LF endings, and max line length 130 (`.editorconfig`, `.flake8`).  
Follow Django naming norms: `snake_case` for functions/variables, `PascalCase` for classes, and clear app-scoped module names (for example, `payment/tests/views/test_save_new_view.py`).  
Keep views thin when possible and move reusable business logic into `utils.py` or dedicated service helpers.

## Testing Guidelines
Primary framework is Django’s built-in test runner (`python manage.py test`).  
Place tests either as `app/tests.py` or package-style under `app/tests/` with files named `test_*.py`.  
Add or update tests for every behavior change, especially endpoints, serializers, and management commands (see `payment/tests/` and `financial/tests/` patterns). No explicit coverage threshold is configured.

## Commit & Pull Request Guidelines
Recent history follows Conventional Commit style: `feat(scope): ...`, `fix(scope): ...`, `test(scope): ...`, `refactor(scope): ...`. Keep subject lines imperative and scoped to one app when possible.  
For PRs, include: concise summary, impacted apps/endpoints, migration notes, test evidence (`make test` output), and linked issue/task. Call out environment or config changes explicitly.

## Security & Configuration Tips
Use `.env.example` as the template for local `.env` values. Never commit secrets (email credentials, API keys, or production settings). Validate settings changes across `development.py` and `production.py` before merge.
