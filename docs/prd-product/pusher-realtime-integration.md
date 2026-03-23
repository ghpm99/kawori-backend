## 1. Feature Overview

- Name: Pusher Realtime Integration
- Summary: Handles pusher webhook events and private channel authentication for realtime modules.
- Target user: Backend integration with realtime clients and admins.
- Business value: Supports secure realtime communications and channel presence/state updates.

## 2. Problem Statement

- Realtime modules need validated webhooks and channel auth handshake.
- Without this, events are untrusted and private channels cannot be safely used.

## 3. Current Behavior

- Webhook endpoint validates signature using pusher client.
- Handles webhook event types:
  - `channel_occupied` / `channel_vacated` to publish status events.
  - `client_event` for `client-screen` updates persisted to `Config`.
- Auth endpoint parses `socket_id` and `channel_name` and returns pusher auth payload.

## 4. User Flows

### 4.1 Main Flow

1. Pusher posts webhook event.
2. Backend validates signature and processes event.
3. Backend emits status updates or stores client-screen payload.

### 4.2 Alternative Flows

1. Admin-authenticated client requests private channel auth.
2. Backend returns auth response from pusher SDK.

### 4.3 Error Scenarios

- Invalid webhook signature returns error response.
- Missing auth parameters can lead to invalid downstream auth behavior.

## 5. Functional Requirements

- The system must validate and process pusher webhooks.
- The system must support private channel auth endpoint.

## 6. Business Rules

- Webhook endpoint is audit-logged as auth action.
- Auth endpoint requires `admin` group.

## 7. Data Model (Business View)

- Uses `remote.Config` as storage for latest screen payload event.

## 8. Interfaces

- APIs:
  - `/pusher/webhook`
  - `/pusher/auth`

## 9. Dependencies

- Depends on pusher app credentials and channel conventions.
- Used by remote-control feature.

## 10. Limitations / Gaps

- Auth payload parsing is manual string split and not URL-decoder robust.

## 11. Opportunities

- Add stronger payload parsing and validation.
- Add event dead-letter logging for unexpected webhook events.

## 12. Acceptance Criteria

- Given valid webhook signature, when webhook is posted, then event is processed and success response returned.
- Given admin and valid socket/channel params, when auth endpoint is called, then pusher auth payload is returned.

## 13. Assumptions

- Pusher channel names/events remain consistent with connected clients.
