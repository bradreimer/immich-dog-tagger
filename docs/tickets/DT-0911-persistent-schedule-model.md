# Tickets

## ID
DT-0911

## Related spec
v0.9.1 Scheduling & Automation

## Priority
High

## Status
Completed

## Goal
Add persistent schedule definitions to `state.db`.

## Context
v0.9.0 provides persistent pipeline jobs. Scheduling configuration must survive application and container restarts.

## Implementation notes
- Inspect the actual v0.9.0 SQLAlchemy models and migration approach.
- Add a typed schedule model following existing conventions.
- Represent the operation using existing job-operation types where possible.
- Persist enabled state, schedule expression, timezone semantics, timestamps, and execution metadata.
- Provide an idempotent representation of a scheduled occurrence.
- Associate scheduled jobs with their originating schedule.
- Do not add scheduler execution behavior yet.

## Acceptance criteria
- Schedules persist in `state.db`.
- Enabled/disabled state persists.
- Invalid definitions are rejected.
- Timezone semantics are explicit.
- Configuration survives restart.
- A scheduled occurrence can be identified uniquely.

## Testing requirements
- Model tests.
- Persistence tests.
- Validation tests.
- Schedule/timezone tests.
- Database regression tests.

## Dependencies
v0.9.0 job infrastructure

## Suggested commit message
`feat(scheduler): add persistent schedule model`
