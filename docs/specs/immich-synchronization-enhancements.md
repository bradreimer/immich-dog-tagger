# Immich Synchronization Enhancements

## Purpose
Improve synchronization reliability and diagnostics between Immich and local workflow state.

## User Story
As an operator, I want sync runs to be repeatable and transparent so I can trust that local state reflects Immich consistently.

## Goals
- Make sync behavior idempotent.
- Improve failure classification and retry behavior.
- Provide clear visibility into sync progress and checkpoints.

## Non-goals
- Replacing Immich as the source system.
- Distributed multi-instance synchronization.

## Requirements
- Re-running sync must not produce inconsistent duplicates.
- Retry behavior must distinguish transient from permanent errors.
- Sync diagnostics must expose last successful checkpoints.
- Error output must be actionable for operators.

## Acceptance Criteria
- Idempotency and retry behavior are covered by automated tests.
- Failure scenarios produce explicit diagnostics.
- Operators can verify sync health from status/API output.

## Open Questions
- Should checkpoint storage be per album, per asset, or both?
