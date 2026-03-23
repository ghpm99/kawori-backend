## 1. Feature Overview

* Name: Facetexture Character Composer
* Summary: Black Desert character roster management plus background preview/export image composition with class symbols.
* Purpose: Provide game-specific visual composition and character metadata management.
* Business value: User engagement feature for the BDO community segment.

## 2. Current Implementation

* How it works today: `facetexture/views.py` offers character CRUD-like operations and image processing endpoints using PIL.
* Main flows: list characters, create/update/reorder/delete character entries, preview composed background, export ZIP of cropped character panels.
* Entry points (routes, handlers, jobs): `/facetexture/*` endpoints, plus class symbol/image retrieval routes.
* Key files involved (list with paths):
  * `facetexture/views.py`
  * `facetexture/models.py`
  * `facetexture/application/use_cases/*.py`
  * `kawori/utils.py` (sprite extraction helpers)
  * `facetexture/management/commands/ONEOFF_*.py`

## 3. Architecture & Design

* Layers involved (frontend/backend): view -> use case -> ORM + PIL image operations.
* Data flow (step-by-step): user uploads background -> server resizes/crops grid -> overlays class symbols -> returns preview image or writes zip export.
* External integrations: none.
* State management (if applicable): character rows persisted with order/show/class; legacy JSON `Facetexture` model still present.

## 4. Data Model

* Entities involved: `Character`, `BDOClass`, `PreviewBackground`, `Facetexture`.
* Database tables / schemas: facetexture app tables with image fields.
* Relationships: character belongs to user and one BDO class.
* Important fields: `order`, `show`, `active`, class assets (`image`, `class_image`, `color`, `class_order`).

## 5. Business Rules

* Explicit rules implemented in code: max 44 active characters per user; icon style restricted to `P/G/D`; delete operation is soft delete (`active=False`).
* Edge cases handled: missing background upload returns 400; missing characters returns 400/404 depending endpoint.
* Validation logic: serializer-based request validation for most endpoints.

## 6. User Flows

* Normal flow: user creates characters -> uploads background -> previews composition -> downloads zip export.
* Error flow: invalid class/id/style/background payload yields 4xx.
* Edge cases: reorder uses raw SQL updates to shift order window atomically.

## 7. API / Interfaces

* Endpoints: config/save/class/preview/download/new and per-character reorder/change/delete/class-asset routes under `/facetexture/`.
* Input/output: JSON for metadata operations; multipart form for preview/download background image; binary image/zip responses for assets.
* Contracts: class asset endpoints return PNG buffers.
* Internal interfaces: helper functions build class symbol/image URLs from route names.

## 8. Problems & Limitations

* Technical debt: coexistence of old JSON model (`Facetexture`) and normalized `Character` model.
* Bugs or inconsistencies: ZIP export writes fixed file `export.zip` in current working directory, creating concurrency risk.
* Performance issues: image processing is synchronous and CPU-bound in request thread.
* Missing validations: no explicit upload size/type limits for background file.

## 9. Security Concerns ⚠️

* Any suspicious behavior: local filesystem write/delete on fixed filename (`export.zip`) and open file wrapper use in response path.
* External code execution: none.
* Unsafe patterns: predictable temporary filename can cause collisions/race conditions across concurrent requests.
* Injection risks: low SQL injection risk (raw SQL reorder query is parameterized).
* Hardcoded secrets: none.
* Unsafe file/system access: file operations occur in request path without isolated temp directory usage.

## 10. Improvement Opportunities

* Refactors: replace fixed export filename with secure per-request temp file.
* Architecture improvements: offload heavy image jobs to async worker and object storage.
* Scalability: cache generated class symbols and thumbnails.
* UX improvements: progress feedback and export presets.

## 11. Acceptance Criteria

* Functional: users in `blackdesert` group can manage characters and generate previews/exports.
* Technical: class/style validations and ordering logic remain consistent.
* Edge cases: missing files/invalid IDs return stable errors.

## 12. Open Questions

* Unknown behaviors: intended lifecycle for legacy `Facetexture.characters` JSON blob.
* Missing clarity in code: storage/retention policy for generated zip artifacts.
* Assumptions made: media sprite files exist at configured paths.
