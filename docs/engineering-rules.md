# Engineering Rules

## Objective

This repository will adopt release automation based on semantic versioning and Conventional Commits. These rules are mandatory because the automation depends on predictable commit history, explicit version ownership, and explicit registration of operational actions.

## Mandatory rules for every change

1. Every code change must exist in a commit.
2. Every commit must contain a single logical change.
3. Every commit that may reach `develop` or `main` must follow Conventional Commits.
4. Every behavior change must include tests or a documented justification when tests are not practical.
5. Every change that requires a one-off script, data correction, recalculation, or manual operational step must be registered in `scripts.xml`.
6. Every registered one-off must also be documented in `docs/oneoff-registry.md`.
7. Workflow changes must update the relevant document in `docs/` in the same change set.

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
```

## Allowed commit types

- `feat`: new behavior, usually a minor bump
- `fix`: bug fix, usually a patch bump
- `refactor`: internal restructuring with no intended behavior change
- `test`: automated tests only
- `docs`: documentation only
- `build`: pipeline, dependency, packaging, or infrastructure changes
- `chore`: housekeeping that should not affect release notes

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

## Branch and release policy

- `develop` is the integration branch.
- `main` is the stable release branch.
- Release automation will prepare a PR from `develop` to `main`.
- Merging that PR is the release approval point.

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

## Review checklist

Before merging a change, verify:

- commit message follows Conventional Commits
- scope reflects the affected domain
- tests were added or updated when behavior changed
- migrations are present when schema changed
- `scripts.xml` was updated when a one-off is required
- `docs/` was updated when the workflow or operational behavior changed
