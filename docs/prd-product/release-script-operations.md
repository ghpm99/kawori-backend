## 1. Feature Overview

- Name: Release Script Operations
- Summary: Registers and executes one-off/operational release scripts up to a target semantic version with execution tracking.
- Target user: Engineering/operations admins.
- Business value: Ensures required data/backfill scripts run consistently during releases.

## 2. Problem Statement

- Releases often require one-off tasks beyond code deploy.
- Without orchestration, critical migration/backfill steps are skipped or duplicated.

## 3. Current Behavior

- Reads script registry from `scripts.xml` with version + command entries.
- Supports pending script selection by target version and executed history.
- Executes commands through `run_release_scripts` with `--target-version` and optional `--dry-run`, `--force`, `--include-operational`.
- Persists execution records in `ReleaseScriptExecution`.

## 4. User Flows

### 4.1 Main Flow

1. Operator runs command with target version.
2. System loads pending scripts <= target version.
3. System executes each command and records success/failure.

### 4.2 Alternative Flows

1. Dry-run lists pending scripts without execution.
2. Force mode ignores prior successful execution history.

### 4.3 Error Scenarios

- Invalid semantic version format.
- Registered command missing in Django command registry.
- Script command exception marks execution as failed and halts with error.

## 5. Functional Requirements

- The system must parse semantic versions and script registry entries.
- The system must persist execution audit for each script.
- Operator can preview pending scripts before execution.

## 6. Business Rules

- Only one-off commands run by default unless `--include-operational` is set.
- Scripts beyond target version are excluded.
- Previously successful scripts are skipped unless forced.

## 7. Data Model (Business View)

- `ReleaseScriptExecution`: release version, script name, status, output, start/finish timestamps.

## 8. Interfaces

- CLI command: `python manage.py run_release_scripts --target-version <vX.Y.Z>`.
- Registry source: `scripts.xml`.

## 9. Dependencies

- Depends on command registration and scripts registry discipline.
- Uses audit app models for execution history.

## 10. Limitations / Gaps

- No transactional rollback across multiple scripts.
- Registry format is raw XML fragments, sensitive to malformed entries.

## 11. Opportunities

- Add pre-flight validation and dependency ordering constraints.
- Add release report export for change management.

## 12. Acceptance Criteria

- Given target version and pending scripts, when command runs, then each script is executed and status persisted.
- Given `--dry-run`, when command runs, then scripts are listed and none executed.

## 13. Assumptions

- Script commands are idempotent or explicitly designed for one-time execution.
