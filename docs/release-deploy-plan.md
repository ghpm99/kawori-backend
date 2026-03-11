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

## Recommended tooling

Preferred first implementation:

- `release-please`

Why:

- creates an explicit release PR
- keeps the release decision visible
- reduces accidental bumps
- is easier to learn and inspect than a fully implicit release flow

Alternative for a later stage:

- `python-semantic-release`

Why not first:

- it is more automatic
- it hides more of the release preparation step
- it is better after commit discipline is already stable

## CI and workflow split

Recommended workflow separation:

1. `ci.yml`
   - formatting
   - lint
   - security
   - tests
2. `release.yml`
   - runs on `develop`
   - creates or updates the release PR
3. `publish.yml`
   - runs on merge to `main`
   - creates tag and GitHub Release if needed
4. `deploy.yml`
   - runs on release publish or tag push
   - deploys to the VM or triggers the remote deploy script

## Deploy strategy

Recommended implementation path:

### Phase 1: assisted deploy

- release automation publishes the tag and release
- operator enters the VM and runs a single deploy script

This keeps server access manual while removing repetitive release work.

### Phase 2: full deploy

- GitHub Actions connects to the VM through SSH
- it runs the same deploy script remotely

This preserves one deploy path and avoids duplicated logic.

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

## One-off execution contract

One-offs are part of the release contract.

The deploy flow must eventually execute a command such as:

```text
python manage.py run_release_scripts --target-version vX.Y.Z
```

That command should read `scripts.xml`, determine pending items for the target version, execute them safely, and record completion.

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
