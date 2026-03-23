## 1. Feature Overview

- Name: Facetexture Character Composer
- Summary: Lets users manage a roster of BDO characters and generate preview/download background packs with class icon overlays.
- Target user: Black Desert users creating profile showcases.
- Business value: Provides personalized visual output and game-community engagement utility.

## 2. Problem Statement

- Users need a quick way to organize character roster and produce themed visual exports.
- Without this, roster presentation is manual and inconsistent.

## 3. Current Behavior

- Returns active character configuration ordered by `order`.
- Supports create character, rename, class change, icon visibility toggle, reorder, soft delete.
- Enforces max 44 active characters per user.
- Provides class list and class image/symbol assets.
- Preview endpoint composites resized background grid with optional class symbols.
- Download endpoint exports per-character cropped images into ZIP.

## 4. User Flows

### 4.1 Main Flow

1. User creates characters and reorders roster.
2. User uploads background to preview.
3. System returns composed PNG preview.
4. User requests download and receives ZIP export.

### 4.2 Alternative Flows

1. User toggles class icon visibility per character.
2. User changes class or character name.

### 4.3 Error Scenarios

- Missing background file for preview/download.
- Invalid icon style symbol.
- Character/class not found.
- Max character limit reached.

## 5. Functional Requirements

- The system must manage user-scoped character roster state.
- The system must provide preview and export generation from uploaded background.
- The user can manage class/name/order/visibility per character.

## 6. Business Rules

- Character cap: 44 active characters.
- Delete action is soft delete (`active=false`).
- Reorder operation updates destination and shifts surrounding rows in SQL transaction.
- Icon style accepted values: `P`, `G`, `D`.

## 7. Data Model (Business View)

- `Character`: user roster entry with class, order, visibility.
- `BDOClass`: class metadata + assets.
- `Facetexture`: JSON fallback config per user (legacy).

## 8. Interfaces

- APIs under `/facetexture/`:
  - config, save, class list, preview, download, new, and character-specific actions (`reorder`, `change-class`, `change-name`, `change-visible`, `delete`, `get-symbol-class`, `get-image-class`).

## 9. Dependencies

- Depends on media assets in `media/bdoclass` and `media/classimage`.
- Uses PIL image processing.

## 10. Limitations / Gaps

- Export file naming uses character names directly; duplicate/special characters can be problematic.
- Some payload validations are serializer-backed but business constraints are still permissive.

## 11. Opportunities

- Add template presets and watermark/branding options.
- Add persistent export history and share links.

## 12. Acceptance Criteria

- Given valid character payload, when creating character, then character appears in config list.
- Given valid background upload, when preview is requested, then composed PNG is returned.
- Given valid download request, when processed, then ZIP file is returned.

## 13. Assumptions

- Frontend handles upload size constraints and previews user-facing errors.
