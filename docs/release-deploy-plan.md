# Release And Deploy Plan

## Objective

Automate versioning, release creation, and deployment while keeping the process explicit and easy to audit.

## Target workflow

1. Development happens on `develop`.
2. CI validates every push and pull request.
3. Release automation inspects the commit history on `develop`.
4. Automation proposes the next semantic version and opens or updates a release PR from `develop` to `main`.
5. The release PR includes:
   - semantic version bump
   - changelog summary
   - release metadata
6. Approval and merge of that PR is the explicit release decision.
7. Merge into `main` triggers:
   - validation pipeline
   - tag creation in the format `vX.Y.Z`
   - GitHub Release creation
   - deployment workflow or deploy-ready state
8. The VM updates to the released tag and executes pending one-offs.

## Why this design

- `develop` remains the working branch.
- `main` remains the stable release branch.
- Version bumps are derived from commit history instead of manual memory.
- Approval still exists at the release boundary.
- Deployment can be automated without changing the release decision model.

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

- release automation
- runtime introspection
- deploy scripts
- operational checks

## Semantic versioning rules

- `fix` -> patch bump
- `feat` -> minor bump
- `BREAKING CHANGE` or `!` -> major bump
- `docs`, `test`, `refactor`, `build`, and `chore` do not bump unless configured otherwise

## Implemented tooling

This repository implements release preparation with repository-local scripts plus GitHub Actions instead of `release-please`.

Reason:

- the required workflow is `develop -> automatic PR to main -> merge publishes release`
- generic release tools work best when they prepare releases on the target branch itself
- a local script keeps the SemVer rules explicit and easy to inspect

Implemented components:

- `scripts/prepare_release.py`: computes the next version from Conventional Commits, updates `kawori/version.py`, and refreshes `CHANGELOG.md`
- `.github/workflows/release-pr.yml`: prepares or updates the release PR from `develop` to `main`
- `.github/workflows/publish.yml`: publishes the tag and GitHub Release after merge to `main`
- `scripts/extract_release_notes.py`: extracts the matching changelog section for the release body

Operational guarantees in the current automation:

- the release branch is created from `origin/main` and `develop` is merged into it, ensuring version files and changelog never conflict with `main`
- the next version is compared against tags already merged into `main`, not arbitrary tags from unrelated branch history
- the release branch is always force-pushed when a release is needed, avoiding stale release PR branches
- PR lookup is repository-scoped and filters by `owner:branch` so reruns update the existing release PR instead of attempting a duplicate
- new changelog entries are inserted at the top (newest first) rather than appended

## CI and workflow split

Recommended workflow separation:

1. `ci.yml`
   - formatting
   - lint
   - security
   - tests
2. `release-pr.yml`
   - runs on `develop`
   - creates or updates the release PR
3. `publish.yml`
   - runs on merge to `main`
   - creates tag and GitHub Release if needed
4. VM deploy script
   - runs manually on the server
   - updates checkout to the selected tag
   - installs dependencies, migrates, runs one-offs, and optionally restarts the service

## Deploy strategy

Recommended implementation path:

### Phase 1: assisted deploy

- release automation publishes the tag and release
- operator enters the VM and runs a single deploy script

This keeps server access manual while removing repetitive release work.

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
- integrate release automation
- generate release PRs from `develop`

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

1. commit changes to feature branches using Conventional Commits
2. merge into `develop`
3. automation prepares the release PR
4. approve and merge the release PR into `main`
5. release and deploy happen with little or no manual intervention
