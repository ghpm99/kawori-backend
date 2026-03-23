## 1. Feature Overview

- Name: Remote Device Control
- Summary: Allows admins to send remote keyboard/mouse/command actions and upload screenshots via realtime channel.
- Target user: Admin operators.
- Business value: Enables remote operational control and monitoring of connected display/client.

## 2. Problem Statement

- Operations require remote command and visual monitoring from backend tools.
- Without this, support/control actions require direct physical/device access.

## 3. Current Behavior

- Endpoints forward actions to pusher events: send command, hotkey, keypress, mouse move/button/scroll/combo.
- Screen size endpoint reads last reported config value.
- Screenshot endpoint stores uploaded image at fixed record and notifies clients.
- Keyboard keys endpoint returns predefined allowable key list.

## 4. User Flows

### 4.1 Main Flow

1. Admin sends remote action request.
2. Backend publishes action event to realtime channel.
3. Connected client executes action.

### 4.2 Alternative Flows

1. Admin uploads screenshot.
2. Backend stores file and sends notification event.

### 4.3 Error Scenarios

- Missing screenshot file in upload.
- Missing config record for screen size.
- Permission denied for non-admin users.

## 5. Functional Requirements

- The system must publish remote actions to realtime channel.
- The system must persist latest screenshot image.
- The system should expose available keyboard key set.

## 6. Business Rules

- All remote endpoints require `admin` group.
- Screenshot save replaces existing screenshot file (`screenshot.png`).

## 7. Data Model (Business View)

- `Config`: stores screen config JSON payload.
- `Screenshot`: stores uploaded image reference.

## 8. Interfaces

- APIs under `/remote/`:
  - `send-command`, `screen-size`, `hotkey`, `key-press`, `mouse-move`, `mouse-button`, `save-screenshot`, `mouse-scroll`, `mouse-move-and-button`, `keyboard-keys`.

## 9. Dependencies

- Depends on pusher event transport and connected client behavior.

## 10. Limitations / Gaps

- No explicit command acknowledgement/receipt tracking.
- No rate limiting for high-frequency control events.

## 11. Opportunities

- Add session-based remote control locks.
- Add command execution audit timelines and playback.

## 12. Acceptance Criteria

- Given admin request for mouse move, when endpoint is called, then event is published and success response returned.
- Given screenshot upload, when endpoint is called, then screenshot is saved and notification emitted.

## 13. Assumptions

- Client is subscribed and online to consume realtime actions.
