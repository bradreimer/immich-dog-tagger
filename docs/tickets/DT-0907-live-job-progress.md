# DT-0907

## ID
DT-0907

## Related spec
v0.9.0 Mission Control Foundation

## Priority
Medium

## Status
Planned

## Goal
Make Mission Control visibly track jobs while they execute.

## Context
The user needs to know whether a long-running detection or embedding job is progressing without refreshing the page.

## Implementation notes
- Use polling initially unless repository constraints strongly favor another existing mechanism.
- Re-fetch active/recent job state at a reasonable interval.
- Show progress bars or counts where available.
- Show current operation and useful timing information.
- Stop polling when no active jobs remain.
- Do not introduce WebSockets solely for this ticket.

## Acceptance criteria
- Active job state updates without a full page refresh.
- Progress changes are reflected in the UI.
- Completed/failed transitions appear automatically.
- Polling stops when no longer needed.
- Browser navigation remains responsive.

## Testing requirements
- UI polling tests.
- Tests for running -> completed.
- Tests for running -> failed.
- Build and lint.

## Dependencies
DT-0906

## Suggested commit message
`feat(ui): show live pipeline progress`
