.PHONY: build run makemigrations migrate test version run-release-scripts restore-dump activate-run ci release-main-ff

CI_TEST_ENV = DJANGO_SETTINGS_MODULE=kawori.settings.test \
	SECRET_KEY=ci-test-secret-key \
	POSTGRES_DB=kawori \
	POSTGRES_USER=postgres \
	POSTGRES_PASSWORD=postgres \
	POSTGRES_HOST=127.0.0.1 \
	POSTGRES_PORT=5432 \
	POSTGRES_TEST_DB=test_kawori \
	BASE_URL=http://localhost:8000 \
	BASE_URL_WEBHOOK=http://localhost:8100 \
	BASE_URL_FRONTEND=http://localhost:3000 \
	BASE_URL_FRONTEND_FINANCIAL=http://localhost:5173 \
	COOKIE_DOMAIN=localhost \
	ENV_PUSHER_APP_ID=1 \
	ENV_PUSHER_KEY=ci-pusher-key \
	ENV_PUSHER_SECRET=ci-pusher-secret \
	ENV_PUSHER_CLUSTER=mt1

CI_SQLITE_TEST_ENV = DJANGO_SETTINGS_MODULE=kawori.settings.test_sqlite \
	SECRET_KEY=ci-test-secret-key \
	BASE_URL=http://localhost:8000 \
	BASE_URL_WEBHOOK=http://localhost:8100 \
	BASE_URL_FRONTEND=http://localhost:3000 \
	BASE_URL_FRONTEND_FINANCIAL=http://localhost:5173 \
	COOKIE_DOMAIN=localhost \
	ENV_PUSHER_APP_ID=1 \
	ENV_PUSHER_KEY=ci-pusher-key \
	ENV_PUSHER_SECRET=ci-pusher-secret \
	ENV_PUSHER_CLUSTER=mt1

build:
	python manage.py collectstatic --no-input

run:
	python manage.py runserver --settings=kawori.settings.development

makemigrations:
	python manage.py makemigrations --settings=kawori.settings.development

migrate:
	python manage.py migrate --settings=kawori.settings.development

test:
	python manage.py test --settings=kawori.settings.development

version:
	python manage.py app_version --settings=kawori.settings.development

run-release-scripts:
	python manage.py run_release_scripts --target-version=$(VERSION) --settings=kawori.settings.development

restore-dump:
	psql -U postgres -h localhost -c "drop database kawori;"
	psql -U postgres -h localhost -c "create database kawori;"
	psql -U postgres -h localhost kawori < ~/dump/kawori.tar

activate-run:
	.venv/bin/python3.13 manage.py runserver --settings=kawori.settings.development

# Local mirror of .github/workflows/ci.yml quality gate validations.
ci:
	black --check .
	isort --check-only --profile black .
	flake8 .
	bandit -r . -x ./.venv,./**/migrations -s B105,B106
	pip-audit -r requirements.txt
	@if python -c "import socket; s=socket.socket(); s.settimeout(0.5); s.connect(('127.0.0.1',5432)); s.close()" >/dev/null 2>&1; then \
		echo "Using PostgreSQL test settings (kawori.settings.test)"; \
		$(CI_TEST_ENV) python manage.py check; \
		$(CI_TEST_ENV) python manage.py makemigrations --check --dry-run; \
		$(CI_TEST_ENV) python manage.py test; \
	else \
		echo "PostgreSQL not available, using SQLite test settings (kawori.settings.test_sqlite)"; \
		$(CI_SQLITE_TEST_ENV) python manage.py check; \
		$(CI_SQLITE_TEST_ENV) python manage.py makemigrations --check --dry-run; \
		$(CI_SQLITE_TEST_ENV) python manage.py test; \
	fi

release-main-ff:
	@echo ""
	@echo "======== Release Main (fast-forward local) ========"
	@CURRENT_BRANCH=$$(git branch --show-current) && \
	if [ -z "$$CURRENT_BRANCH" ]; then \
		echo "FAILED: Could not determine current branch" && exit 1; \
	fi && \
	if ! git diff-index --quiet HEAD --; then \
		echo "FAILED: Working tree has uncommitted changes" && exit 1; \
	fi && \
	if ! git diff --cached --quiet; then \
		echo "FAILED: Staging area has uncommitted changes" && exit 1; \
	fi && \
	git fetch origin --tags && \
	git checkout develop && \
	git pull --ff-only origin develop && \
	git merge origin/main -m "build(sync): merge main into develop" && \
	git push origin develop && \
	git checkout main && \
	git pull --ff-only origin main && \
	git merge --ff-only origin/develop && \
	git restore --source=origin/main --staged --worktree CHANGELOG.md kawori/version.py && \
	RELEASE_OUTPUT=$$(mktemp) && \
	GITHUB_OUTPUT="$$RELEASE_OUTPUT" python scripts/prepare_release.py --base-ref origin/main --head-ref HEAD && \
	RELEASE_NEEDED=$$(awk -F= '$$1=="release_needed"{print $$2}' "$$RELEASE_OUTPUT") && \
	if [ "$$RELEASE_NEEDED" != "true" ]; then \
		rm -f "$$RELEASE_OUTPUT"; \
		echo "No releasable changes found between main and develop."; \
		git checkout "$$CURRENT_BRANCH"; \
		exit 0; \
	fi && \
	RELEASE_VERSION=$$(awk -F= '$$1=="version"{print $$2}' "$$RELEASE_OUTPUT") && \
	RELEASE_TAG=$$(awk -F= '$$1=="tag"{print $$2}' "$$RELEASE_OUTPUT") && \
	rm -f "$$RELEASE_OUTPUT" && \
	git add kawori/version.py CHANGELOG.md && \
	git commit -m "build(release): prepare v$$RELEASE_VERSION" && \
	if git rev-parse "$$RELEASE_TAG" >/dev/null 2>&1 || git ls-remote --tags --refs origin "$$RELEASE_TAG" | grep -q .; then \
		echo "FAILED: Tag $$RELEASE_TAG already exists (local or remote)." && exit 1; \
	fi && \
	git tag -a "$$RELEASE_TAG" -m "Release $$RELEASE_TAG" && \
	git push origin main && \
	git push origin "$$RELEASE_TAG" && \
	git checkout develop && \
	git merge --ff-only main && \
	git push origin develop && \
	git checkout "$$CURRENT_BRANCH"
	@echo "Release finished with local fast-forward, release commit, tag and develop sync."
