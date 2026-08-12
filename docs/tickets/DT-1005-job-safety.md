# DT-1005: Job lifecycle, idempotency, and recovery

## **ID**

DT-1005

## **Related spec**

[v1.0.0 Product & Engineering Specification](../specs/v1.0.0.md) -- FR-4, responsible architectural guidelines #4/#5

## **Priority**

High

## **Status**

Completed

## **Goal**

Make long-running pipeline/reclassification operations safe to operate.

## **Context**

The existing `PipelineJob` system already provided queued/running/completed/failed states and single-flight locking. This ticket's job was to confirm Reclassify (DT-1001) actually inherits those guarantees correctly, and to close the one real gap that reuse exposed: a `ClassificationPass` has no exception handler left to run if the process hosting it is killed outright rather than raising.

## **Implementation notes**

- Reclassify (DT-1001) runs through the existing `PipelineJobRunner`/`PipelineJobRepository`/`PipelineJobService`, so it inherits, with no new code: queued/running/completed/failed states, single-flight execution (`has_running_job` rejects a second concurrent run), start/end timestamps, and error persistence.
- Closed a real gap this reuse exposed: `ClassificationPass` rows are only ever driven synchronously inside one job execution, so a pass still `RUNNING` at process startup is, by definition, orphaned by a crash that never reached its exception handler. `job_recovery.recover_interrupted_jobs()` now also reconciles any `RUNNING` `ClassificationPass` to `FAILED` at startup (mirroring the existing `PipelineJob` RUNNING->FAILED behavior), so a killed Reclassify never shows as silently still-active.
- `ClassificationPass.job_id` is now threaded from the job handler (`progress.job.id`) so a pass can always be traced back to (and reconciled via) its owning job.
- Partial-batch safety (DT-1001): Reclassify commits per-batch, so a mid-run failure preserves already-completed batches and can be retried without corrupting state or losing reviewed labels (reviewed rows are never selected in the first place).

## **Acceptance criteria**

- A killed or failed operation can be retried without duplicating logical records or losing reviewed state.
- Stale passes are reconciled to a terminal state on restart rather than appearing to still be running.
- Partial batches never corrupt database state.

## **Testing requirements**

`tests/test_job_recovery.py` (orphaned RUNNING pass -> FAILED on recovery, completed pass untouched) plus the DT-1001 batching/failure tests in `tests/test_reclassify.py`.

## **Dependencies**

DT-1000, DT-1001.

## **Suggested commit message**

`fix(DT-1005): reconcile orphaned classification passes on restart`
