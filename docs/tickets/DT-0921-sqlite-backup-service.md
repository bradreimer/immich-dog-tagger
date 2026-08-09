# Tickets

## ID
DT-0921

## Related spec
v0.9.2 Data Safety & Recovery

## Priority
High

## Status
Planned

## Goal
Implement a reliable SQLite-aware backup service for `state.db`.

## Context
`state.db` is the authoritative source of truth. A live SQLite file must not be treated as a generic static file for backup purposes.

## Implementation notes
- Inspect the existing database/session lifecycle.
- Use SQLite backup semantics appropriate to the current SQLAlchemy setup.
- Make backup destination explicit.
- Include timestamped or otherwise unique backup identity.
- Do not silently overwrite a known-good backup.
- Return useful backup metadata.
- Fail clearly on I/O or SQLite errors.
- Keep the service independent of CLI/UI presentation.

## Acceptance criteria
- A consistent backup can be created while the application is running.
- The backup opens successfully as SQLite.
- Backup failures are reported.
- Existing backups are not silently destroyed.
- Backup metadata identifies when it was created.
- The active database is unchanged by backup.

## Testing requirements
- Backup creation test.
- SQLite integrity/readability test.
- Existing-backup protection test.
- Failure-path test.
- Database regression tests.

## Dependencies
v0.9.0 database infrastructure

## Suggested commit message
`feat(backup): add sqlite state database backup service`
