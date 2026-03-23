## 1. Feature Overview

* Name: Discord Integration
* Summary: Read-only admin endpoints exposing Discord-related users/guilds/members/roles from existing DB tables.
* Purpose: Operational visibility into Discord integration data.
* Business value: Supports moderation/ops dashboards.

## 2. Current Implementation

* How it works today: `discord/views/*` call use cases that run raw SQL `SELECT` queries and paginate in memory.
* Main flows: fetch users, guilds, guild members, guild roles.
* Entry points (routes, handlers, jobs): `/discord/user/`, `/discord/guild/`, `/discord/guild/member/`, `/discord/guild/role/`.
* Key files involved (list with paths):
  * `discord/views/user.py`
  * `discord/views/guild.py`
  * `discord/application/use_cases/*.py`
  * `discord/urls.py`

## 3. Architecture & Design

* Layers involved (frontend/backend): view -> use case -> raw SQL through Django connection.
* Data flow (step-by-step): request page param -> SQL fetch all rows -> map dicts -> paginate helper.
* External integrations: none in this module (assumes tables are populated by another system).
* State management (if applicable): read-only projections.

## 4. Data Model

* Entities involved: implied external tables `user_discord`, `guild_discord`, `member_discord`, `role_discord`.
* Database tables / schemas: raw table names above (not Django models in app).
* Relationships: implicit foreign keys by id columns.
* Important fields: discord ids, banned flags, names, activity timestamps.

## 5. Business Rules

* Explicit rules implemented in code: user endpoint requires `discord` group; guild/member/role endpoints require `admin` group.
* Edge cases handled: none specific beyond pagination.
* Validation logic: no query filter validation besides page.

## 6. User Flows

* Normal flow: authorized user queries list endpoint and pages through records.
* Error flow: unauthorized access rejected by decorator.
* Edge cases: absent/empty tables return empty paginated output.

## 7. API / Interfaces

* Endpoints: `GET /discord/user/`, `GET /discord/guild/`, `GET /discord/guild/member/`, `GET /discord/guild/role/`.
* Input/output: query `page`; JSON paginated arrays.
* Contracts: list row fields mirror raw SQL select columns.
* Internal interfaces: use cases directly embed SQL query strings.

## 8. Problems & Limitations

* Technical debt: no ORM model ownership for queried tables.
* Bugs or inconsistencies: data access fetches full tables before pagination, which may not scale.
* Performance issues: full table scans and memory pagination.
* Missing validations: no filtering/search parameters.

## 9. Security Concerns ⚠️

* Any suspicious behavior: raw SQL is static and parameter-free, so injection risk is low but table exposure risk exists.
* External code execution: none.
* Unsafe patterns: dependency on unmanaged tables can bypass model-level constraints.
* Injection risks: low in current fixed queries.
* Hardcoded secrets: none.
* Unsafe file/system access: none.

## 10. Improvement Opportunities

* Refactors: map unmanaged Django models for schema control.
* Architecture improvements: add server-side pagination in SQL (`LIMIT/OFFSET`).
* Scalability: index-based filtering and search endpoints.
* UX improvements: add filters (guild, banned, active) and sort options.

## 11. Acceptance Criteria

* Functional: authorized users can retrieve discord datasets from all four endpoints.
* Technical: endpoints remain read-only.
* Edge cases: empty datasets return valid paginated structure.

## 12. Open Questions

* Unknown behaviors: source process populating Discord tables is not present in repository.
* Missing clarity in code: data freshness SLA for discord snapshots.
* Assumptions made: table schemas remain stable externally.
