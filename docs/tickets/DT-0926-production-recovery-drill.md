# Tickets

## ID
DT-0926

## Related spec
v0.9.2 Data Safety & Recovery

## Priority
High

## Status
Completed

## Goal
Prove the backup, restore, job recovery, and derived-data recovery paths work together.

## Context
Production confidence requires a tested recovery procedure, not merely implemented commands.

## Implementation notes
- Create a disposable copy/environment based on production-like state.
- Perform a real state database backup.
- Verify the backup.
- Simulate database loss or replacement.
- Restore the backup.
- Validate review history, identities, classifications, and embedding examples.
- Simulate an interrupted job.
- Exercise the recovery path.
- Remove or invalidate selected derived artifacts and rebuild them.
- Record exact commands and expected outcomes.
- Do not experiment destructively on the only production database or Immich library.

## Acceptance criteria
- Recovery drill completes successfully.
- Restored database contains expected authoritative state.
- Review history survives restore.
- Learned examples survive restore.
- Interrupted jobs have a documented recovery path.
- Derived artifacts can be rebuilt.
- Recovery commands are documented.
- A fresh operator can follow the procedure without relying on undocumented knowledge.

## Testing requirements
- Full recovery drill.
- Database integrity verification.
- Review/learning state verification.
- Job recovery verification.
- Derived-data rebuild verification.
- Full `./scripts/check.sh`.

## Dependencies
DT-0921, DT-0922, DT-0923, DT-0924, DT-0925

## Suggested commit message
`docs(recovery): document and validate production recovery`
