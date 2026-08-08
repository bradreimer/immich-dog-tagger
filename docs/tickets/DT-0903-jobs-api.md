# DT-0903

## ID
DT-0903

## Related spec
v0.9.0 Mission Control Foundation

## Priority
High

## Status
Completed

## Goal
Expose persistent jobs and job execution through FastAPI.

## Context
Mission Control needs a stable backend contract for starting and inspecting operations.

## Implementation notes
- Inspect existing API route organization, schemas, dependency injection, and error handling.
- Add endpoints for listing jobs, retrieving one job, creating a job, and cancelling a job if cancellation is supported safely.
- Reuse the job service and runner rather than implementing execution in route handlers.
- Define typed request/response schemas.
- Preserve existing API conventions.

## Acceptance criteria
- The API can list recent jobs.
- The API can retrieve a specific job.
- The API can request a new supported operation.
- The API reports job lifecycle and progress.
- Invalid operations return a clear validation error.
- Existing API tests continue to pass.

## Testing requirements
- API endpoint tests.
- Validation/error tests.
- Job creation integration test.
- Regression tests for existing routes.

## Dependencies
DT-0902

## Suggested commit message
`feat(api): expose pipeline jobs`
