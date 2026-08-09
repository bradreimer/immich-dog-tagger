# Tickets

## ID
DT-0925

## Related spec
v0.9.2 Data Safety & Recovery

## Priority
Medium

## Status
Planned

## Goal
Give Mission Control a focused operational diagnostics view.

## Context
Mission Control is becoming the primary control surface. The user needs to understand system health without reading container logs for routine diagnosis.

## Implementation notes
- Inspect the existing Mission Control shell and job/scheduler views.
- Reuse existing status APIs where possible.
- Show application/database health.
- Show scheduler status.
- Show running/stuck/failed jobs.
- Show last successful backup and backup status where available.
- Show missing derived-data warnings where available.
- Link diagnostics to the relevant operation rather than duplicating entire job views.
- Keep this intentionally small.

## Acceptance criteria
- Mission Control indicates overall application health.
- Scheduler health is visible.
- Recent failures are visible.
- Active/stuck jobs are visible.
- Backup status is visible.
- Derived-data warnings are visible when detected.
- The UI makes clear when manual recovery is required.
- Existing Job Queue, Review, and Schedule workflows remain usable.

## Testing requirements
- Component tests.
- Healthy-state test.
- Failure-state test.
- Scheduler-down test.
- Backup-warning test.
- Missing-derived-data test.
- TypeScript build and lint.

## Dependencies
DT-0924, v0.9.1 Mission Control

## Suggested commit message
`feat(ui): add operational diagnostics to mission control`
