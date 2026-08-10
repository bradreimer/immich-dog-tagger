# Tickets

## ID
DT-0917

## Related spec
v0.9.1 Scheduling & Automation

## Priority
High

## Status
Completed

## Goal
Make unattended scheduling observable, restart-safe, and resilient.

## Context
The scheduler runs when the user is not watching it, so failures must be visible and isolated.

## Implementation notes
- Log scheduler startup/shutdown.
- Log schedule evaluation and skipped/conflicting occurrences.
- Record schedule provenance on jobs.
- Expose scheduler health/status through existing infrastructure.
- Prevent one job failure from terminating the scheduler.
- Reconcile persisted schedules after restart.
- Ensure disabled schedules remain disabled.
- Make operational errors actionable.
- Follow existing logging architecture.

## Acceptance criteria
- Scheduler lifecycle is logged.
- Scheduled jobs identify their source schedule.
- Individual failures do not stop scheduling.
- Conflicting work is handled safely.
- Restart preserves schedules.
- Restart does not duplicate a completed occurrence.
- Disabled schedules remain disabled after restart.
- Mission Control can determine scheduler health.
- Scheduler failures are visible in diagnostics.
- `./scripts/check.sh` passes.

## Testing requirements
- Failure-isolation tests.
- Restart/reconciliation tests.
- Duplicate-occurrence tests.
- Concurrency/conflict tests.
- Disabled-schedule restart test.
- Scheduler health/status tests.
- Full `./scripts/check.sh`.

## Dependencies
DT-0916

## Suggested commit message
`feat(scheduler): harden scheduling and observability`
