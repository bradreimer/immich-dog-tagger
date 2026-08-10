# Tickets

## ID
DT-0914

## Related spec
v0.9.1 Scheduling & Automation

## Priority
High

## Status
Completed

## Goal
Expose schedule management and scheduler status through FastAPI.

## Context
Mission Control needs an API contract for configuring and observing automation.

## Implementation notes
- Inspect actual v0.9.0 API route/schema/dependency patterns.
- Add list/get/create/update operations.
- Add enable/disable operations.
- Add Run Now.
- Add delete/archive only if appropriate to the schedule lifecycle.
- Expose next/last execution information.
- Keep scheduler logic in services, not route handlers.
- Follow existing validation/error conventions.

## Acceptance criteria
- Schedules can be listed and retrieved.
- Valid schedules can be created and edited.
- Schedules can be enabled/disabled.
- Run Now creates a normal manual job.
- Next/last execution information is available.
- Invalid definitions return useful API errors.
- Existing APIs remain intact.

## Testing requirements
- CRUD tests.
- Validation tests.
- Enable/disable tests.
- Run Now integration test.
- Error-path tests.
- API regression tests.

## Dependencies
DT-0913

## Suggested commit message
`feat(api): expose scheduler controls`
