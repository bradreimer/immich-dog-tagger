# TICKET 05: Job lifecycle, idempotency, and recovery

## Goal
Make long-running pipeline/reclassification operations safe to operate.

## Steps
1. Reuse the existing job system if present.
2. Define queued/running/completed/failed states.
3. Prevent duplicate project-scoped runs.
4. Make retries safe.
5. Record start/end times, counts, and errors.
6. Detect or recover stale jobs according to the existing runtime model.
7. Ensure partial batches do not corrupt database state.

## Done when
A killed or failed operation can be retried without duplicating logical records or losing reviewed state.
