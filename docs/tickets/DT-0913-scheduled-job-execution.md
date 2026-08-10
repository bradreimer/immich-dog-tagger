# Tickets

## ID
DT-0913

## Related spec
v0.9.1 Scheduling & Automation

## Priority
High

## Status
Completed

## Goal
Turn due schedule occurrences into normal `PipelineJob` executions.

## Context
Mission Control, CLI operations, and scheduled operations must share one execution path.

## Implementation notes
- Inspect the completed v0.9.0 job creation and runner APIs.
- Create one persistent job per due occurrence.
- Record schedule ID and scheduled-occurrence provenance.
- Submit jobs through the existing runner.
- Make occurrence creation idempotent.
- Respect existing conflict/concurrency behavior.
- Define and document the missed-occurrence policy.
- Do not execute pipeline services directly from the scheduler.

## Acceptance criteria
- A due schedule creates a persistent job.
- The existing job runner executes it.
- Scheduled jobs identify their originating schedule.
- The same occurrence cannot create duplicate jobs.
- Conflicting work follows existing job semantics.
- One failed job does not stop unrelated schedules.
- Browser availability has no effect.

## Testing requirements
- Scheduler-to-runner integration test.
- Duplicate-occurrence test.
- Conflict/concurrency test.
- Failure-isolation test.
- Restart/reconciliation test.
- Missed-occurrence test.

## Dependencies
DT-0912, v0.9.0 job runner

## Suggested commit message
`feat(scheduler): execute due schedules as pipeline jobs`
