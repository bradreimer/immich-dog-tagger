# Tickets

## ID
DT-0922

## Related spec
v0.9.2 Data Safety & Recovery

## Priority
High

## Status
Planned

## Goal
Expose safe backup and restore operations through the CLI.

## Context
Recovery must be possible even when the web UI is unavailable.

## Implementation notes
- Inspect existing CLI command structure and output conventions.
- Add commands/subcommands for backup and restore following project conventions.
- Validate a backup before restore.
- Verify it is a readable SQLite database.
- Create a rollback copy of the current database before replacement.
- Require explicit user intent for restore.
- Do not silently restore or overwrite state.
- Make paths and results clear in command output.

## Acceptance criteria
- User can create a backup from the CLI.
- User can validate a backup.
- User can explicitly restore a validated backup.
- Current state is preserved as a rollback point before restore.
- Invalid backups are rejected without changing active state.
- Restore failures do not silently destroy the current database.
- Help text documents the commands.

## Testing requirements
- CLI backup test.
- CLI validation test.
- Successful restore test.
- Invalid-backup test.
- Rollback-point test.
- Failure-path tests.

## Dependencies
DT-0921

## Suggested commit message
`feat(cli): add state backup and restore commands`
