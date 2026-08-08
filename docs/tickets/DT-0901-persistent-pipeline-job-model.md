# DT-0901

## ID
DT-0901

## Related spec
v0.9.0 Mission Control Foundation

## Priority
High

## Status
Completed

## Goal
Introduce a persistent job model representing every pipeline operation.

## Context
Mission Control, the API, CLI, and future scheduler need a common representation of work. Job state must survive browser refreshes and process restarts.

## Implementation notes
- Inspect the existing SQLAlchemy models, enums, database initialization, and migration/versioning approach before implementation.
- Add a strongly typed pipeline operation value covering scan, detect, embed, classify, learn, sync, and full pipeline.
- Add a persistent job model with lifecycle state.
- Include created, started, and completed timestamps as appropriate.
- Include progress fields appropriate to the existing data model.
- Add a repository/service abstraction consistent with the project architecture.
- Follow the repository's existing migration strategy rather than inventing a second one.

## Acceptance criteria
- A job can be persisted and retrieved.
- Jobs identify the pipeline operation they represent.
- Valid lifecycle transitions are enforced.
- Invalid lifecycle transitions are rejected.
- Job state survives a process restart.
- Existing database behavior remains intact.

## Testing requirements
- Model tests.
- Lifecycle transition tests.
- Persistence/repository tests.
- Regression coverage for existing database behavior.

## Dependencies
None.

## Suggested commit message
`feat(jobs): add persistent pipeline job model`
