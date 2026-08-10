# Tickets

## ID
DT-0924

## Related spec
v0.9.2 Data Safety & Recovery

## Priority
High

## Status
Completed

## Goal
Make interrupted and stuck PipelineJobs recoverable after process or container failure.

## Context
v0.9.1 introduced unattended scheduling. A scheduler restart must not leave jobs permanently stuck or silently mark incomplete work as successful.

## Implementation notes
- Inspect the actual PipelineJob state machine from v0.9.0/v0.9.1.
- Identify jobs left active during application restart.
- Define safe restart reconciliation.
- Reuse existing retry/failure semantics.
- Preserve job history.
- Make retry/recovery visible to Mission Control.
- Avoid automatically rerunning operations whose effects cannot be safely duplicated unless the existing operation is explicitly idempotent.

## Acceptance criteria
- Interrupted active jobs are detected after restart.
- No interrupted job is silently reported as successful.
- Jobs have a clear recoverable/failed state.
- Safe jobs can be retried.
- Unsafe jobs require explicit user action.
- Scheduled jobs retain schedule provenance.
- Recovery does not create duplicate successful work.

## Testing requirements
- Process-interruption simulation.
- Restart reconciliation test.
- Retry test.
- Unsafe-rerun test.
- Scheduled-job recovery test.
- Job history regression tests.

## Dependencies
v0.9.1 scheduler/job runner

## Suggested commit message
`feat(jobs): add interrupted job recovery`
