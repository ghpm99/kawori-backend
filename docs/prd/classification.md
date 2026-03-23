## 1. Feature Overview

* Name: Classification Voting
* Summary: Question/answer voting by BDO class and combat style, with aggregated summaries and class-level vote analytics.
* Purpose: Capture and aggregate community voting data.
* Business value: Drives insight features for gameplay/class preference analysis.

## 2. Current Implementation

* How it works today: `classification/views.py` exposes question/answer retrieval, vote registration, totals, per-class counts, and summarized resumes.
* Main flows: user submits answer vote; scheduled command processes votes into `AnswerSummary`.
* Entry points (routes, handlers, jobs): `/classification/get-question/`, `/get-answer/`, `/register-answer/`, `/total-votes/`, `/answer-by-class/`, `/get-answer-summary/`; management command `process_votes`.
* Key files involved (list with paths):
  * `classification/views.py`
  * `classification/models.py`
  * `classification/application/use_cases/*.py`
  * `classification/management/commands/process_votes.py`

## 3. Architecture & Design

* Layers involved (frontend/backend): view -> use case -> ORM; offline aggregation command.
* Data flow (step-by-step): vote request -> validate ids/types -> create `Answer`; periodic command computes weighted averages and writes `AnswerSummary.resume` JSON.
* External integrations: none.
* State management (if applicable): answer status fields and summary snapshots by class.

## 4. Data Model

* Entities involved: `Question`, `Answer`, `AnswerSummary`, `Path`, `BDOClass`, `User`.
* Database tables / schemas: classification tables plus FK to facetexture class table.
* Relationships: answers belong to question/class/user; summaries belong to class.
* Important fields: vote, combat style, `height` (vote weight multiplier), summary JSON.

## 5. Business Rules

* Explicit rules implemented in code: vote and combat style must be integers; question/class IDs required; summary processing can filter by last affected path date.
* Edge cases handled: missing IDs/invalid types return 400.
* Validation logic: lightweight payload checks in use case.

## 6. User Flows

* Normal flow: user fetches questions/classes -> submits votes -> later consumes aggregated summaries.
* Error flow: invalid payload or missing records yields error.
* Edge cases: summary command updates existing summary or creates new one.

## 7. API / Interfaces

* Endpoints:
  * `GET /classification/get-question/`
  * `GET /classification/get-answer/`
  * `POST /classification/register-answer/`
  * `GET /classification/get-class/`
  * `GET /classification/total-votes/`
  * `GET /classification/answer-by-class/`
  * `GET /classification/get-answer-summary/`
* Input/output: JSON request for registration and list-based JSON responses.
* Contracts: class endpoints expose image/symbol URLs from facetexture module.
* Internal interfaces: management command computes weighted vote averages.

## 8. Problems & Limitations

* Technical debt: use case uses `.get()` without exception handling for missing question/class, which can raise unhandled exceptions.
* Bugs or inconsistencies: truthiness checks (`if not vote`) reject valid zero vote values.
* Performance issues: summary command loops all answers/classes in Python.
* Missing validations: no explicit bounds for vote values.

## 9. Security Concerns ⚠️

* Any suspicious behavior: none critical.
* External code execution: none.
* Unsafe patterns: command and use cases rely on broad assumptions about referential integrity.
* Injection risks: low.
* Hardcoded secrets: none.
* Unsafe file/system access: none.

## 10. Improvement Opportunities

* Refactors: harden registration with serializer-enforced schema and explicit `DoesNotExist` handling.
* Architecture improvements: incremental aggregation with DB-side calculations.
* Scalability: index and materialize summary projections.
* UX improvements: clearer validation messages and vote constraints.

## 11. Acceptance Criteria

* Functional: users can list questions/answers/classes, register votes, and read summaries.
* Technical: summaries reflect weighted vote calculations.
* Edge cases: invalid IDs/types are rejected without server errors.

## 12. Open Questions

* Unknown behaviors: intended valid vote range is not specified.
* Missing clarity in code: scheduling strategy for `process_votes` command.
* Assumptions made: `height` is intentional vote weighting and not residual test data.
