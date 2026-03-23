## 1. Feature Overview

- Name: Discord Data Directory
- Summary: Exposes paginated views of Discord users, guilds, members, and roles stored in database tables.
- Target user: Admin/Discord operators.
- Business value: Enables administrative visibility into Discord ecosystem entities tied to operations.

## 2. Problem Statement

- Teams need quick lookup of Discord entities from backend data store.
- Without it, operators depend on ad-hoc DB access.

## 3. Current Behavior

- Endpoints execute raw SQL select on `user_discord`, `guild_discord`, `member_discord`, `role_discord`.
- Responses are paginated in-memory list payloads.
- Access control varies by endpoint: user list requires `discord` group; guild/member/role require `admin`.

## 4. User Flows

### 4.1 Main Flow

1. Operator requests entity endpoint.
2. System queries corresponding table.
3. System returns paginated list.

### 4.2 Alternative Flows

- Operator navigates between users/guilds/members/roles endpoints.

### 4.3 Error Scenarios

- Missing token/group permission.
- Underlying table/schema mismatch would fail query.

## 5. Functional Requirements

- The system must list Discord entities from persisted data tables.
- The system should paginate list responses.

## 6. Business Rules

- Read-only feature; no write/update APIs.
- Permission policy is endpoint-specific by group.

## 7. Data Model (Business View)

- External-ish tables queried directly: `user_discord`, `guild_discord`, `member_discord`, `role_discord`.

## 8. Interfaces

- APIs:
  - `/discord/user/`
  - `/discord/guild/`
  - `/discord/guild/member/`
  - `/discord/guild/role/`

## 9. Dependencies

- Depends on DB tables populated by external Discord integration processes.

## 10. Limitations / Gaps

- No model-layer abstraction/validation around SQL tables.
- No filtering besides pagination.

## 11. Opportunities

- Add search/filter fields (name, id_discord, banned, guild).
- Add sync-health indicators and last-sync timestamps.

## 12. Acceptance Criteria

- Given authorized user, when requesting each endpoint, then paginated entity rows are returned.

## 13. Assumptions

- Discord tables exist and are maintained outside this module.
