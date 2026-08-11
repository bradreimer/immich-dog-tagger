# TICKET 05: Job lifecycle, idempotency, and recovery

## Status
Completed

## Implementation notes
- Reclassify (DT-1001) runs through the existing `PipelineJobRunner`/`PipelineJobRepository`/`PipelineJobService`, so it inherits, with no new code: queued/running/completed/failed states, single-flight execution (`has_running_job` rejects a second concurrent run), start/end timestamps, and error persistence.
- Closed a real gap this reuse exposed: `ClassificationPass` rows are only ever driven synchronously inside one job execution, so a pass still `RUNNING` at process startup is, by definition, orphaned by a crash that never reached its exception handler. `job_recovery.recover_interrupted_jobs()` now also reconciles any `RUNNING` `ClassificationPass` to `FAILED` at startup (mirroring the existing `PipelineJob` RUNNING->FAILED behavior), so a killed Reclassify never shows as silently still-active.
- `ClassificationPass.job_id` is now threaded from the job handler (`progress.job.id`) so a pass can always be traced back to (and reconciled via) its owning job.
- Partial-batch safety (DT-1001): Reclassify commits per-batch, so a mid-run failure preserves already-completed batches and can be retried without corrupting state or losing reviewed labels (reviewed rows are never selected in the first place).
- Tests: `tests/test_job_recovery.py` (orphaned RUNNING pass -> FAILED on recovery, completed pass untouched) plus the existing DT-1001 batching/failure tests in `tests/test_reclassify.py`.

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
