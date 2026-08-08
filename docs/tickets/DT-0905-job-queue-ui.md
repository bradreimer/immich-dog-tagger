# DT-0905

## ID
DT-0905

## Related spec
v0.9.0 Mission Control Foundation

## Priority
High

## Status
Completed

## Goal
Provide an Immich-style Job Queue view for Dog Tagger pipeline operations.

## Context
The user wants to see what is running, queued, completed, or failed at a glance.

## Implementation notes
- Reuse the jobs API.
- Group jobs by meaningful lifecycle state.
- Display operation, status, progress, timestamps, and useful failure information.
- Keep the view useful for both active work and recent history.
- Avoid premature real-time transport complexity.

## Acceptance criteria
- Running jobs are clearly identifiable.
- Pending jobs are clearly identifiable.
- Completed and failed jobs are visible in history.
- Progress is displayed when available.
- Job details can be inspected sufficiently to diagnose failures.

## Testing requirements
- UI tests for state rendering.
- Tests for empty, running, completed, and failed queues.
- Build and lint.

## Dependencies
DT-0904

## Suggested commit message
`feat(ui): add job queue view`
