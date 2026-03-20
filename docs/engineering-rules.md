# Engineering Rules

## Objective

This repository uses local release orchestration based on semantic versioning and Conventional Commits. These rules are mandatory because release reliability depends on predictable commit history, explicit version ownership, and explicit registration of operational actions.

## Mandatory rules for every change

1. Every code change must exist in a commit.
2. Every commit must contain a single logical change.
3. Every commit that may reach `develop` or `main` must follow Conventional Commits.
4. Every behavior change must include tests or a documented justification when tests are not practical.
5. Every change that requires a one-off script, data correction, recalculation, or manual operational step must be registered in `scripts.xml`.
6. Every registered one-off must also be documented in `docs/oneoff-registry.md`.
7. Workflow changes must update the relevant document in `docs/` in the same change set.
8. Every AI prompt used in production flows must be registered in `ai/prompts/registry.yaml` with its versioned template file in `ai/prompts/`.
9. Prompt overrides in database must be created and activated only by users in the `AI_PROMPT_EDITOR` group and must include `change_reason`.
10. Every AI execution that depends on prompts must keep prompt traceability metadata (`prompt_key`, `prompt_source`, `prompt_version`, `prompt_hash`).

## Commit convention

Use this format:

```text
type(scope): short imperative summary
```

Examples:

```text
feat(payment): add monthly summary endpoint
fix(financial): correct report amount aggregation
refactor(authentication): isolate token validation helper
test(invoice): cover fixed invoice regeneration flow
docs(release): document deploy workflow
build(ci): add release preparation workflow
build(release): prepare v1.6.0
build(sync): merge main into develop
```

## Allowed commit types

- `feat`: new behavior, usually a minor bump
- `fix`: bug fix, usually a patch bump
- `refactor`: internal restructuring, release as patch
- `test`: automated tests only, release as patch
- `docs`: documentation only, release as patch
- `build`: pipeline, dependency, packaging, or infrastructure changes, release as patch
- `chore`: housekeeping, release as patch when it reaches `develop`

## Breaking changes

Mark backward-incompatible changes explicitly:

```text
feat(payment)!: rename report response keys
```

Or:

```text
BREAKING CHANGE: report clients must read total_open instead of value_open
```

Breaking changes trigger a major version bump and must be deliberate.

## Version bump policy

Current release tooling uses these rules:

- `BREAKING CHANGE` or `!` -> major
- `feat` -> minor
- `fix`, `refactor`, `test`, `docs`, `build`, and `chore` -> patch

This repository intentionally releases every merged change that reaches `main`, even when the change is operational or documentation-oriented. That keeps deployed state, tags, changelog, and repository history aligned.

Release-generated commits are excluded from release calculation and changelog generation when they match the reserved release or sync signatures, such as `build(release): ...`, `build(sync): ...`, and the legacy `chore(release): ...`.

## Branch and release policy

- `develop` is the integration branch.
- `main` is the stable release branch.
- Releases are executed locally with `make release-main-ff`.
- The command must sync `develop` with `origin/main` before attempting the release fast-forward, using a conflict-free history merge (`-s ours`) when branches diverge.
- The command must restore `kawori/version.py` and `CHANGELOG.md` from `origin/main` before recalculating release metadata.
- The command must create `build(release): prepare vX.Y.Z`, tag `vX.Y.Z`, and push `main`.
- After publishing, the command must fast-forward `develop` to `main` to keep release metadata aligned.

## One-off policy

Use one-offs for actions that are not normal Django schema migrations, such as:

- data backfills
- recalculation of derived values
- cleanup tasks
- external sync corrections
- release-only scripts that should run once

If a change requires one of those actions, it is incomplete until:

1. the one-off is registered in `scripts.xml`
2. the one-off is documented in `docs/oneoff-registry.md`
3. the deploy flow knows when and how to run it

## AI prompt governance

The AI prompt source of truth is code-first:

- file catalog: `ai/prompts/registry.yaml` + `ai/prompts/<domain>/<name>.txt`
- optional runtime override: `ai.PromptOverride` managed via Django Admin

Operational rules:

- treat prompt text changes as behavior changes and review them in PR
- never edit active override payload directly; clone a new version and activate it
- temporary overrides should define validity window (`valid_from` / `valid_until`)
- use `AI_PROMPT_DB_OVERRIDE_ENABLED` to control rollout by environment

## Review checklist

Before merging a change, verify:

- commit message follows Conventional Commits
- scope reflects the affected domain
- tests were added or updated when behavior changed
- migrations are present when schema changed
- `scripts.xml` was updated when a one-off is required
- `docs/` was updated when the workflow or operational behavior changed
