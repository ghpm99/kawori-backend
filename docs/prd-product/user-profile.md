## 1. Feature Overview

- Name: User Profile & Group Visibility
- Summary: Returns authenticated user profile and group names.
- Target user: Logged-in users.
- Business value: Enables frontend personalization and permission-aware UI behavior.

## 2. Problem Statement

- Users and UI need identity and permission context.
- Without this, frontend cannot determine role-based navigation.

## 3. Current Behavior

- `GET /profile/` returns serialized current user.
- `GET /profile/groups/` returns list of group names for current user.
- Both endpoints require authenticated cookie and `user` group permission.

## 4. User Flows

### 4.1 Main Flow

1. User calls profile endpoint.
2. System validates JWT cookie and group membership.
3. System returns user profile data.

### 4.2 Alternative Flows

1. User calls groups endpoint.
2. System returns list of role groups.

### 4.3 Error Scenarios

- Missing/invalid token returns unauthorized/forbidden.
- Missing group permission returns forbidden.

## 5. Functional Requirements

- The system must return current user identity payload.
- The system must return current user group names.

## 6. Business Rules

- Access gate uses `validate_user("user")` decorator.
- Authorization derives from JWT cookie user ID and group membership.

## 7. Data Model (Business View)

- `User` with standard profile fields.
- Django `Group` membership relation.

## 8. Interfaces

- APIs: `/profile/`, `/profile/groups/`.

## 9. Dependencies

- Depends on authentication cookie/session and group model.

## 10. Limitations / Gaps

- No endpoint for profile update/preferences (only read).

## 11. Opportunities

- Add editable profile settings.
- Add explicit permission matrix endpoint.

## 12. Acceptance Criteria

- Given valid logged-in user, when requesting `/profile/`, then user data is returned.
- Given valid logged-in user, when requesting `/profile/groups/`, then group names are returned.

## 13. Assumptions

- Serializers expose fields expected by frontend.
