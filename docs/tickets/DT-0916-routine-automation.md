# Tickets

## ID
DT-0916

## Related spec
v0.9.1 Scheduling & Automation

## Priority
Medium

## Status
Completed

## Goal
Make the scheduler useful for the normal unattended Dog Tagger workflow.

## Context
The user should be able to schedule routine processing instead of manually chaining scan/detect/embed/classify/learn/sync commands.

## Implementation notes
- Inspect completed v0.9.0 pipeline/job operations first.
- Prefer existing full-pipeline orchestration for routine new-photo processing.
- Support scheduled learning from accumulated review corrections.
- Support scheduled Immich synchronization using existing sync behavior.
- Do not duplicate pipeline orchestration.
- Keep manual operations available.
- Do not introduce destructive automation.
- Document recommended defaults without making them mandatory.

## Acceptance criteria
- A configured routine schedule processes new work using existing semantics.
- Scheduled learning uses accumulated review corrections.
- Scheduled sync uses existing sync behavior.
- Automation works with browser closed.
- Manual operation remains available.
- No second pipeline orchestration path is introduced.

## Testing requirements
- End-to-end routine automation test.
- No-new-work test.
- Review-correction-to-learning test.
- Scheduled-sync test.
- Manual-operation regression tests.

## Dependencies
DT-0913, DT-0915

## Suggested commit message
`feat(scheduler): add routine automation policies`
