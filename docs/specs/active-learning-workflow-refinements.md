# Active Learning Workflow Refinements

## Purpose
Strengthen the review-to-learning feedback loop so corrections produce reliable and observable model improvements.

## User Story
As an operator, I want review actions to update learner state consistently so that repeated corrections improve future predictions.

## Goals
- Ensure review actions are applied exactly once to learning state.
- Prevent conflicting or stale learning updates.
- Improve observability of learning workflow health.

## Non-goals
- Automated model retraining pipelines.
- Human-review UI redesign.

## Requirements
- Review action ingestion must be idempotent.
- Conflicts and stale updates must be detected and surfaced.
- Learning state updates must be traceable to review actions.
- Status endpoints/commands must expose actionable workflow signals.

## Acceptance Criteria
- Duplicate review events do not duplicate learning updates.
- Conflict paths are handled deterministically and tested.
- Operators can inspect active-learning health with clear signals.

## Open Questions
- What is the preferred policy for conflict resolution: last-write-wins or strict rejection?
