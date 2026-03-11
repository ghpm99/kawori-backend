# One-Off Registry

## Objective

Track every release-specific operational action that must execute outside normal request handling and outside regular schema migration logic.

## Source of truth

The registry has two layers:

1. `scripts.xml`: machine-readable release script index
2. this document: human-readable intent, execution rules, and history

Both must be updated together whenever a new one-off is introduced.

## When a one-off is required

Register a one-off when a change needs:

- data backfill
- recalculation of stored values
- repair of inconsistent records
- external integration correction
- a release-only script that should run once

Do not use a one-off when the change should be a normal Django migration or ordinary application logic.

## Required record for each one-off

Every one-off must define:

- target version
- unique script identifier
- objective
- expected idempotency
- execution trigger
- rollback or retry notes

## `scripts.xml` format

Current format:

```xml
<script version="1.4.0">ONEOFF_20251106_CONTRACT_TO_TAG</script>
```

Recommended conventions:

- use semantic version compatible with the release target
- keep the script identifier stable
- prefer identifiers like `ONEOFF_YYYYMMDD_description`
- reserve non-oneoff operational jobs for clearly named entries such as cron or maintenance tasks

## Registration workflow

When introducing a new one-off:

1. implement the script or management command
2. add the entry to `scripts.xml`
3. add the entry to the table below
4. document how the deploy process should execute it
5. document idempotency expectations

## Execution policy

The deploy flow must execute only pending one-offs for the target version.

Every one-off should be:

- idempotent when possible
- explicit about prerequisites
- logged before and after execution
- recorded as executed in persistent storage

## Registered entries

| Version | Identifier | Type | Objective | Idempotent | Notes |
| --- | --- | --- | --- | --- | --- |
| 1.4.0 | `ONEOFF_20251106_CONTRACT_TO_TAG` | one-off | Associate contract data with tag structure | Unknown | Existing legacy entry from `scripts.xml` |
| 1.4.0 | `ONEOFF_20251113_create_budget_from_users` | one-off | Create budget records from user data | Unknown | Existing legacy entry from `scripts.xml` |
| 1.4.0 | `cron_recalculate_invoices` | operational job | Recalculate invoices | Unknown | Existing entry; confirm whether it should remain here or move to a dedicated job registry |

## Validation checklist

Before merging a change that introduces a one-off, verify:

- the one-off exists in code
- `scripts.xml` contains the target version entry
- this document contains the matching registry entry
- the deploy plan explains when it runs
- the script is safe to re-run or clearly documents why it is not
