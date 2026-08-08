# DT-0902

## ID
DT-0902

## Related spec
v0.9.0 Mission Control Foundation

## Priority
High

## Status
Planned

## Goal
Create the shared service that executes pipeline jobs and records their lifecycle.

## Context
The UI, API, CLI, and future scheduler must invoke one execution path instead of duplicating orchestration logic.

## Implementation notes
- Inspect existing pipeline services and CLI command implementations first.
- Introduce a job runner/orchestration service using dependency injection consistent with the project.
- Map each supported operation to the existing pipeline service.
- Persist Pending -> Running -> Completed/Failed state.
- Capture errors without losing the job record.
- Record progress when the underlying operation can provide it.
- Do not rewrite existing ML pipeline implementations.

## Acceptance criteria
- A queued job can be executed by the shared runner.
- Successful jobs become Completed.
- Exceptions result in Failed jobs with useful diagnostic information.
- Existing pipeline services remain the single implementation of their operations.
- Jobs cannot accidentally execute concurrently when the existing pipeline cannot safely support that.

## Testing requirements
- Runner unit tests.
- Successful execution tests.
- Failure handling tests.
- Dependency-injection tests where applicable.

## Dependencies
DT-0901

## Suggested commit message
`feat(jobs): add pipeline job runner`
