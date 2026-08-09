# Tickets

## ID
DT-0915

## Related spec
v0.9.1 Scheduling & Automation

## Priority
High

## Status
Planned

## Goal
Add schedule configuration and status to Mission Control.

## Context
Normal scheduling should not require SSH, cron editing, or container configuration.

## Implementation notes
- Inspect actual v0.9.0 UI architecture and Mission Control navigation.
- Add a Schedules view/section.
- Show name, operation, schedule, timezone, enabled state, next run, last run, and last result.
- Add create/edit, enable/disable, and Run Now.
- Make disabled automation obvious.
- Preserve Job Queue and Review workflows.
- Reuse existing API/client patterns.

## Acceptance criteria
- User can view all schedules.
- User can create and edit schedules.
- User can enable/disable schedules.
- User can run an operation immediately.
- Next/last execution state is visible.
- Errors and empty states are handled.
- Existing Mission Control workflows remain usable.

## Testing requirements
- Component tests.
- Create/edit tests.
- Enable/disable tests.
- Run Now tests.
- Empty/error-state tests.
- TypeScript build and UI lint.

## Dependencies
DT-0914

## Suggested commit message
`feat(ui): add schedule controls to mission control`
