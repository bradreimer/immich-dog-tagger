# TICKET 01: Reclassification service/job

## Status
Completed

## Implementation notes
- Added `ClassificationPass` model + additive migration (status, classifier_version, threshold, per-decision counts, changed_count, error_message, timestamps).
- Added `CropClassification.classification_pass_id`/`embedding` columns (additive migration) so a crop's embedding is cached once and reused instead of recomputed by every pass.
- Added `services/reclassify.py::ReclassifyService`: only touches `CropClassification` rows with `source == AUTO` (REVIEW/MANUAL rows -- reviewed ground truth -- are never selected), terminates cleanly with an explanatory message when there are no active labeled examples, batches work (default 200/batch) with a commit per batch so a mid-run failure preserves already-completed batches, and stamps `classifier_version`/`classification_pass_id` on every row it touches.
- Wired in as `PipelineOperation.RECLASSIFY` in `services/job_execution.py`, so it runs through the existing `PipelineJobRunner` and inherits queued/running/completed/failed states, single-flight locking, and startup recovery for free.
- Tests: `tests/test_reclassify.py` (zero-example short circuit, ground-truth preservation, embedding reuse, idempotent rerun, batched partial-failure safety) and `tests/test_job_execution_reclassify.py` (handler + full job-runner integration).

## Goal
Implement a backend reclassification operation that reuses stored embeddings and current reviewed examples.

## Steps
1. Add a project-scoped reclassification service using the existing classifier.
2. Load only valid labeled examples and eligible crops.
3. Batch nearest-neighbor work.
4. Preserve authoritative reviewed labels.
5. Persist prediction, score, decision state, classifier/config version, and pass/job ID.
6. Make repeated execution idempotent.
7. Handle zero-example projects cleanly.
8. Record counts, duration, and failure details.

## Done when
The service can safely reclassify an existing project without scanning, downloading, detecting, or recomputing already-valid embeddings.
