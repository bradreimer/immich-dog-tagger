# Tickets

## ID
DT-0912

## Related spec
v0.9.1 Scheduling & Automation

## Priority
High

## Status
Completed

## Goal
Implement deterministic schedule evaluation and scheduler lifecycle management.

## Context
The application needs a long-running component that determines when schedules are due without depending on the browser.

## Implementation notes
- Inspect existing application startup/lifecycle patterns.
- Implement a small scheduler service with injected dependencies.
- Use an injectable clock/time source where practical.
- Load enabled schedules.
- Determine due occurrences and calculate next occurrence.
- Keep evaluation separate from job creation/execution.
- Do not call ML or Immich pipeline services directly.

## Acceptance criteria
- Due schedules are detected correctly.
- Future schedules are not triggered early.
- Disabled schedules are ignored.
- Next-run calculations are deterministic.
- Scheduler starts and stops cleanly.
- Scheduler works without a browser.

## Testing requirements
- Due/not-due tests.
- Boundary tests.
- Timezone tests.
- Disabled schedule tests.
- Lifecycle tests.
- Clock injection tests where applicable.

## Dependencies
DT-0911

## Suggested commit message
`feat(scheduler): add schedule evaluation service`
