# DT-0906

## ID
DT-0906

## Related spec
v0.9.0 Mission Control Foundation

## Priority
High

## Status
Planned

## Goal
Allow the user to manually start every supported pipeline operation from Mission Control.

## Context
Normal operation should not require SSH or direct CLI invocation.

## Implementation notes
- Add controls for scan, detect, embed, classify, learn, sync, and full pipeline.
- Each control creates a persistent job through the API.
- Prevent duplicate/conflicting operations where the runner cannot safely execute them concurrently.
- Provide clear feedback when a job is accepted or rejected.
- Reuse the existing pipeline orchestration.

## Acceptance criteria
- Each supported operation can be launched from the UI.
- Starting an operation creates a visible job.
- Conflicting operations are rejected or queued safely.
- The UI communicates failures clearly.
- Existing CLI operations continue to work.

## Testing requirements
- UI interaction tests.
- API job-creation tests.
- Conflict/idempotency tests appropriate to the existing pipeline.

## Dependencies
DT-0905

## Suggested commit message
`feat(ui): add pipeline operation controls`
