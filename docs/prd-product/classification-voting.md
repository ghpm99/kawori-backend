## 1. Feature Overview

- Name: BDO Class Voting & Summaries
- Summary: Collects user votes on class-related questions, aggregates class distributions, and exposes processed summaries.
- Target user: Black Desert community users and public viewers of aggregate stats.
- Business value: Captures community preference intelligence for classes/combat styles.

## 2. Problem Statement

- Community feedback needs structured capture and aggregation.
- Without this, insights remain anecdotal and not queryable.

## 3. Current Behavior

- Authenticated `blackdesert` users can list questions and submit answers.
- Users can list their own answers.
- Public endpoints return class catalog, total votes, answer distribution by class, and answer summaries.
- Background command `process_votes` aggregates answers (weighted by `height`) into `AnswerSummary`.

## 4. User Flows

### 4.1 Main Flow

1. User fetches questions.
2. User submits vote with question, class, combat style.
3. System stores answer and later summary job processes aggregates.

### 4.2 Alternative Flows

1. Public consumers fetch total votes and distribution by class.
2. Consumers fetch precomputed summary payloads.

### 4.3 Error Scenarios

- Missing question/class/combat style/vote fields.
- Invalid field types for combat style or vote.

## 5. Functional Requirements

- The system must record votes per user/question/class/style.
- The system must expose aggregated totals and summaries.

## 6. Business Rules

- Answer status lifecycle exists (`open`, `processing`, `done`) though write path currently creates with default open.
- Weighted vote computation uses `vote * height` during summary processing.
- Summary can be filtered by latest content path date (`Path.affected_class/date_path`) in processing command.

## 7. Data Model (Business View)

- `Question`: question text/details.
- `Answer`: user vote tied to class and combat style.
- `AnswerSummary`: per-class aggregated resume JSON.
- `Path`: optional change timeline used by summarizer.

## 8. Interfaces

- APIs:
  - `/classification/get-question/`
  - `/classification/get-answer/`
  - `/classification/register-answer/`
  - `/classification/get-class/`
  - `/classification/total-votes/`
  - `/classification/answer-by-class/`
  - `/classification/get-answer-summary/`
- Command: `python manage.py process_votes`

## 9. Dependencies

- Depends on `facetexture.BDOClass` catalog.

## 10. Limitations / Gaps

- Some read endpoints are public (no auth decorator), which may be intended but broad.
- Register use case calls `.get()` without exception handling for missing IDs.

## 11. Opportunities

- Add duplicate-vote prevention/update policy per user-question-cycle.
- Add trend-over-time analytics by combat style.

## 12. Acceptance Criteria

- Given valid payload, when user submits answer, then vote is stored.
- Given populated answers, when summary command runs, then per-class summary records are updated/created.
- Given public summary endpoint call, then processed summary data is returned.

## 13. Assumptions

- Operational scheduler executes summary processing command regularly.
