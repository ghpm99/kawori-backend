## 1. Feature Overview

- Name: Tag Management
- Summary: Creates and manages user tags used to categorize invoices and downstream reports/budgets.
- Target user: Financial users.
- Business value: Enables category-level reporting, budget allocation, and organization.

## 2. Problem Statement

- Users need categorization to understand spending/income behavior.
- Without tags, reporting and budget features lose business meaning.

## 3. Current Behavior

- Create tag with name/color.
- Enforce unique tag name per user.
- List tags with aggregated invoice metrics.
- Retrieve tag detail and update name/color.

## 4. User Flows

### 4.1 Main Flow

1. User creates tag.
2. System validates uniqueness for current user.
3. Tag becomes available for invoice assignment.

### 4.2 Alternative Flows

1. User filters tag list by `name__icontains`.
2. User updates tag color/name.

### 4.3 Error Scenarios

- Duplicate tag for same user.
- Tag not found on detail/update.

## 5. Functional Requirements

- The system must create unique user-scoped tags.
- The user can list tag totals and update tag attributes.

## 6. Business Rules

- Tag uniqueness constraint: `(user, name)`.
- Tag list includes totals: invoice count, total value, open, closed.
- Budget-linked tags are marked (`is_budget`) and displayed with `#` prefix in some responses.

## 7. Data Model (Business View)

- `Tag`: name, color, owner.
- Relation to `Invoice` (many-to-many).
- Optional one-to-one relation to `Budget`.

## 8. Interfaces

- APIs:
  - `/financial/tag/`
  - `/financial/tag/new`
  - `/financial/tag/<id>/`
  - `/financial/tag/<id>/save`

## 9. Dependencies

- Used by invoices, payments, budgeting, reports, and CSV import flows.

## 10. Limitations / Gaps

- No native merge/rename conflict resolution for existing duplicate tags.

## 11. Opportunities

- Add tag merge tool with auto-reassignment.
- Add usage trend metadata directly in tag endpoint.

## 12. Acceptance Criteria

- Given unique name, when creating tag, then tag is saved.
- Given duplicate name for same user, when creating tag, then request fails.
- Given existing tag, when updating, then updated fields are persisted.

## 13. Assumptions

- Color validation is handled by serializer constraints.
