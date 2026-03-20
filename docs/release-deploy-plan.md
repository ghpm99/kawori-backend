# Release And Deploy Plan

## Objective

Keep versioning, release creation, and deployment explicit and easy to audit, with release orchestration executed locally.

## Target workflow

1. Development happens on `develop`.
2. CI validates push and pull request changes.
3. Release is executed locally with `make release-main-ff`.
4. The command first syncs `develop` with `origin/main` (merge commit when needed) and pushes `develop`.
5. The command fast-forwards `main` to `develop`, restores release-controlled files from `origin/main`, and recalculates version/changelog.
6. The command creates the release commit `build(release): prepare vX.Y.Z`.
7. The command creates and pushes the annotated tag `vX.Y.Z`.
8. The command fast-forwards `develop` to `main` so release metadata stays aligned.
9. The VM updates to the released tag and executes pending one-offs.

## Why this design

- `develop` remains the working branch.
- `main` remains the stable release branch.
- Release-controlled files must be recalculated from the latest published `main`, not from a drifted state in `develop`.
- Version bumps are derived from commit history instead of manual memory.
- Approval remains explicit because release execution is manual.
- `main` must flow back into `develop` after every release so version and changelog files stay aligned.
- Deployment remains manual and deterministic per release tag.

## Version ownership

The backend must own a canonical application version in code. The recommended location is:

```text
kawori/version.py
```

Recommended structure:

```python
__version__ = "0.0.0"
```

This file becomes the single source of truth for:

- release tooling
- runtime introspection
- deploy scripts
- operational checks

## Semantic versioning rules

- `fix` -> patch bump
- `feat` -> minor bump
- `BREAKING CHANGE` or `!` -> major bump
- `docs`, `test`, `refactor`, `build`, and `chore` -> patch bump
- reserved release commits such as `build(release): ...`, `build(sync): ...`, and legacy `chore(release): ...` are ignored for bump calculation and changelog generation

## Implemented tooling

This repository implements release preparation with repository-local scripts and a local `make` command.

Reason:

- a single-maintainer flow benefits from deterministic local release execution
- local fast-forward release avoids recurrent automation conflicts and stale PR branches
- a local script keeps the SemVer rules explicit and easy to inspect

Implemented components:

- `scripts/prepare_release.py`: computes the next version from Conventional Commits, updates `kawori/version.py`, and refreshes `CHANGELOG.md`
- `Makefile` target `release-main-ff`: orchestrates local release from `develop` to `main`, release commit creation, tag creation, and `develop` sync
- `scripts/extract_release_notes.py`: extracts the matching changelog section for the release body
- `ai/prompt_service.py`: resolves prompts from file catalog with optional DB override and prompt traceability metadata

Operational guarantees in the local release command:

- `main` is fast-forwarded from `origin/develop` before release metadata is recalculated
- `kawori/version.py` and `CHANGELOG.md` are always restored from `origin/main` before the next release version and changelog are generated
- the process stops on any non-fast-forward branch state or dirty working tree
- the next version is compared against tags already merged into `main`, not arbitrary tags from unrelated branch history
- reserved release commits are excluded from the next version calculation and changelog
- new changelog entries are inserted at the top (newest first) rather than appended
- after tag publication, `main` is synced back into `develop` using fast-forward

## AI prompt lifecycle in release flow

Prompt behavior is release-relevant and follows versioned artifacts:

1. Prompts are versioned in code (`ai/prompts/registry.yaml` + template files).
2. Runtime overrides are optional and gated by `AI_PROMPT_DB_OVERRIDE_ENABLED`.
3. Overrides are environment-scoped (`AI_PROMPT_ENVIRONMENT`) and cached with short TTL (`AI_PROMPT_OVERRIDE_CACHE_TTL_SECONDS`).
4. On override save/delete, cache is invalidated through Django signals.
5. Every AI request carries traceability metadata:
   - `prompt_key`
   - `prompt_source` (`file` or `db`)
   - `prompt_version`
   - `prompt_hash`

Operational implication:

- release validation should verify critical prompt keys exist in the file registry before merging
- temporary DB overrides must include validity window and change reason

## CI and release split

Recommended workflow separation:

1. `ci.yml`
   - formatting
   - lint
   - security
   - tests
2. `make release-main-ff`
   - runs locally
   - prepares release metadata, creates release commit, pushes `main`, tags, and syncs `develop`
3. VM deploy script
   - runs manually on the server
   - updates checkout to the selected tag
   - installs dependencies, migrates, runs one-offs, and optionally restarts the service

## Deploy strategy

Recommended implementation path:

### Phase 1: assisted deploy

- local release command publishes the tag
- operator enters the VM and runs a single deploy script

This keeps server access and release control manual while removing repetitive branching work.

### Current stopping point

- GitHub Actions does not connect to the VM automatically
- the server is updated by running `scripts/deploy_release.sh`

This is the intentional Phase 3 boundary.

## VM deploy script responsibilities

The deploy script should:

1. read the currently deployed version
2. fetch remote tags
3. resolve the latest stable release tag
4. stop if the current version is already deployed
5. checkout the target tag
6. install dependencies
7. run Django migrations
8. run pending one-offs
9. restart the application service
10. persist the deployed version and operation log

Implemented file:

```text
scripts/deploy_release.sh
```

## One-off execution contract

One-offs are part of the release contract.

The deploy flow must eventually execute a command such as:

```text
python manage.py run_release_scripts --target-version vX.Y.Z
```

That command should read `scripts.xml`, determine pending items for the target version, execute them safely, and record completion.

Implemented pieces:

- `audit/release_scripts.py`
- `audit.management.commands.run_release_scripts`
- `audit.ReleaseScriptExecution`

## Implementation phases

### Phase 1

- create `docs/`
- normalize tag format to `vX.Y.Z`
- define commit policy
- define one-off registry policy

### Phase 2

- add `kawori/version.py`
- integrate release tooling
- generate release metadata from `develop`

### Phase 3

- create deploy script for the VM
- create one-off executor command in Django
- register executed one-offs in persistent storage

Status:

- completed in repository code

### Phase 4

- automate deploy from GitHub Actions through SSH
- add smoke validation after restart

## Day-to-day result

Expected daily workflow after implementation:

1. commit changes using Conventional Commits
2. merge into `develop`
3. run `make release-main-ff` locally
4. command pushes release commit to `main`, creates tag, and syncs `develop`
5. run deployment on VM with `scripts/deploy_release.sh`
