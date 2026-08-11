# DT-1001: Reclassification service/job

## **ID**

DT-1001

## **Related spec**

[v1.0.0 Product & Engineering Specification](../specs/v1.0.0.md) -- FR-4, FR-5, section 5 (Reclassification behavior)

## **Priority**

High

## **Status**

Completed

## **Goal**

Implement a backend reclassification operation that reuses stored embeddings and current reviewed examples.

## **Context**

v1.0.0's core workflow is review -> reclassify -> review uncertain results -> repeat. Before this ticket there was no way to recompute predictions from newly reviewed examples without re-running the full pipeline, or the existing `ClassificationMode.ALL`, which is unsafe to reuse for this purpose since it overwrites every classification including human-reviewed (`MANUAL`/`REVIEW`) ones. This ticket builds the missing, safe operation, using the DT-1000 audit's plan and the DT-1004 policy module.

## **Implementation notes**

- Added `ClassificationPass` model + additive migration (status, classifier_version, threshold, per-decision counts, changed_count, error_message, timestamps).
- Added `CropClassification.classification_pass_id`/`embedding` columns (additive migration) so a crop's embedding is cached once and reused instead of recomputed by every pass.
- Added `services/reclassify.py::ReclassifyService`: only touches `CropClassification` rows with `source == AUTO` (`REVIEW`/`MANUAL` rows -- reviewed ground truth -- are never selected), terminates cleanly with an explanatory message when there are no active labeled examples, batches work (default 200/batch) with a commit per batch so a mid-run failure preserves already-completed batches, and stamps `classifier_version`/`classification_pass_id` on every row it touches.
- Wired in as `PipelineOperation.RECLASSIFY` in `services/job_execution.py`, so it runs through the existing `PipelineJobRunner` and inherits queued/running/completed/failed states, single-flight locking, and startup recovery for free.

## **Acceptance criteria**

- The service can safely reclassify an existing project without scanning, downloading, detecting, or recomputing already-valid embeddings.
- `REVIEW`/`MANUAL` classifications are never modified.
- Zero-labeled-example projects terminate cleanly instead of mass-unknowning every crop.
- Repeated execution with unchanged inputs is idempotent.
- Counts, duration, and failure details are recorded per pass.

## **Testing requirements**

`tests/test_reclassify.py` (zero-example short circuit, ground-truth preservation, embedding reuse, idempotent rerun, batched partial-failure safety) and `tests/test_job_execution_reclassify.py` (handler + full job-runner integration).

## **Dependencies**

DT-1000, DT-1004.

## **Suggested commit message**

`feat(DT-1001): add reclassification service and job`
