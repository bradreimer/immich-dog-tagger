# Tickets

## ID
DT-0923

## Related spec
v0.9.2 Data Safety & Recovery

## Priority
High

## Status
Completed

## Goal
Make derived artifacts safely disposable and rebuildable without corrupting authoritative state.

## Context
Crops, embeddings, downloads, and model outputs are derived data. The system must distinguish missing derived data from lost application state.

## Implementation notes
- Inventory the actual derived paths and database references.
- Identify which artifacts are authoritative versus rebuildable.
- Detect missing referenced artifacts.
- Provide the smallest useful repair/rebuild operation using existing pipeline commands/services.
- Ensure rebuilding is idempotent.
- Do not delete data automatically as part of repair.
- Report unresolved missing source assets clearly.

## Acceptance criteria
- Missing derived artifacts can be detected.
- Repair does not modify unrelated state.
- Rebuild uses existing pipeline services.
- Rebuild is safe to retry.
- `state.db` remains authoritative.
- User can distinguish recoverable derived-data loss from authoritative-data loss.

## Testing requirements
- Missing-artifact detection tests.
- Rebuild tests.
- Idempotency tests.
- Partial-failure tests.
- Database integrity tests.

## Dependencies
DT-0921

## Suggested commit message
`feat(recovery): detect and rebuild derived data`
