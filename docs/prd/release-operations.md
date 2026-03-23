## 1. Feature Overview

* Name: Release & Deployment Operations
* Summary: Automated semantic version bumping/changelog prep, release tagging flow, deploy script execution, and one-off registry control.
* Purpose: Standardize release governance and post-release operational tasks.
* Business value: Reduces release risk and ensures one-off execution traceability.

## 2. Current Implementation

* How it works today: `scripts/prepare_release.py` computes next version from Conventional Commits; `Makefile release-main-ff` orchestrates branch sync/tagging; deploy script runs migrations/static/release scripts.
* Main flows: analyze git commits -> bump version/changelog -> commit/tag/push -> deploy target tag -> run pending one-offs via `run_release_scripts`.
* Entry points (routes, handlers, jobs): `make release-main-ff`, `scripts/deploy_release.sh`, `python manage.py run_release_scripts --target-version vX.Y.Z`.
* Key files involved (list with paths):
  * `scripts/prepare_release.py`
  * `scripts/extract_release_notes.py`
  * `scripts/deploy_release.sh`
  * `Makefile`
  * `scripts.xml`
  * `audit/management/commands/run_release_scripts.py`
  * `docs/engineering-rules.md`, `docs/oneoff-registry.md`

## 3. Architecture & Design

* Layers involved (frontend/backend): CLI scripts + management commands + git orchestration.
* Data flow (step-by-step): read git history -> infer release type/version -> write version/changelog outputs -> execute release scripts registered for target version.
* External integrations: git CLI, pip install, deployment shell environment.
* State management (if applicable): deployed version file (`.deploy/current_version`) and `ReleaseScriptExecution` DB records.

## 4. Data Model

* Entities involved: `ReleaseScriptExecution` and XML registry entries.
* Database tables / schemas: `release_script_execution`.
* Relationships: none.
* Important fields: release version, script name, status, output, timestamps.

## 5. Business Rules

* Explicit rules implemented in code: Conventional Commit parsing drives semantic bump; one-off/operational scripts read from `scripts.xml`; already-successful scripts skipped unless forced.
* Edge cases handled: no releasable commits aborts release; dry-run supported for release scripts.
* Validation logic: semantic version parsing and registry XML parsing with fail-fast behavior.

## 6. User Flows

* Normal flow: maintainer runs release make target -> release commit and tag generated -> deploy script checks out tag and executes migrations + registered scripts.
* Error flow: missing tag/version/command aborts process.
* Edge cases: release scripts can be included/excluded by one-off prefix policy.

## 7. API / Interfaces

* Interfaces: command-line scripts and make targets.
* Input/output: git refs, target versions, environment vars, generated release metadata files.
* Contracts: `scripts.xml` `<script version="x.y.z">COMMAND</script>` entries.
* Internal interfaces: `audit.release_scripts.get_pending_release_scripts` consumed by `run_release_scripts` command.

## 8. Problems & Limitations

* Technical debt: release/deploy logic depends on many shell assumptions and mutable local git state.
* Bugs or inconsistencies: deploy script executes `eval "$APP_RESTART_COMMAND"` (operator-controlled but high risk).
* Performance issues: full dependency install on each deploy run.
* Missing validations: no cryptographic integrity check for registry/script changes.

## 9. Security Concerns ⚠️

* Any suspicious behavior: dynamic shell evaluation in deploy script and command execution from registry.
* External code execution: yes, intentional command execution (`call_command`, shell eval, pip install).
* Unsafe patterns: `eval` in deploy pipeline; registry-driven command execution requires strict supply-chain controls.
* Injection risks: environment-variable command injection via `APP_RESTART_COMMAND` if not tightly controlled.
* Hardcoded secrets: none, but deployment relies on environment secrets.
* Unsafe file/system access: git checkout and package install run with deploy user privileges.

## 10. Improvement Opportunities

* Refactors: replace `eval` restart call with explicit allowlisted service manager commands.
* Architecture improvements: signed release metadata and immutable artifact deployment.
* Scalability: CI-built artifacts instead of source-based deployment.
* UX improvements: clearer preflight checks and dry-run for full deploy sequence.

## 11. Acceptance Criteria

* Functional: release versioning/tagging and pending script execution run deterministically.
* Technical: release script execution history is persisted and queryable.
* Edge cases: duplicate tags, missing commands, and dry-run mode are handled safely.

## 12. Open Questions

* Unknown behaviors: rollback strategy after partial release-script failures is not fully automated.
* Missing clarity in code: ownership model for production deploy execution permissions.
* Assumptions made: only trusted maintainers can modify registry and deploy environment vars.
