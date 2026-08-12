# DT-1007: Logging and operational diagnostics

## **ID**

DT-1007

## **Related spec**

[v1.0.0 Product & Engineering Specification](../specs/v1.0.0.md) -- FR-8

## **Priority**

Medium

## **Status**

Completed

## **Goal**

Make failures diagnosable without exposing sensitive data.

## **Context**

Job failures were already persisted to the database (`error_message`), but there was no structured application-log trail for the classify/correct/reclassify lifecycle, making it hard to reconstruct what happened around a failure without reading source code.

## **Implementation notes**

- `services/job_runner.py::PipelineJobRunner._run()` now logs start (job id, operation), successful completion (duration), and failure (duration, error message) for every `PipelineOperation` -- this covers the whole pipeline/reclassification lifecycle from one place rather than requiring each handler to log separately.
- `ClassificationService.classify()` logs stage/mode and resulting counts (classified, unknown) -- counts only, no crop paths.
- `ClassificationCorrectionService.correct()` logs `classification_id`, previous identity, and new identity -- explicitly never the crop's file path (regression-tested).
- Reclassify already had start/complete/failure logging with counts and duration from DT-1001; `job_recovery.py` already logs startup reconciliation counts from DT-1005.
- Stale vs. active job/pass distinction: DT-1005's recovery reconciliation plus these lifecycle logs mean a stuck job/pass has both a log trail (last successful tick) and a DB status (`FAILED` with an explanatory `error_message`) rather than an ambiguous `RUNNING` with no context.
- UI already surfaces actionable errors: the diagnostics "Recent failures" card (pre-existing) and the new Learning Progress "Last Reclassify: Failed" state (DT-1006).

## **Acceptance criteria**

- A failed reclassification can be diagnosed from application logs and UI status without inspecting source code.
- Logs contain counts, durations, identifiers, and stage names -- never image contents, file paths, or secrets.
- Stale jobs/passes are distinguishable from active ones.

## **Testing requirements**

`tests/test_logging.py` asserts logs are emitted on both the success and failure paths and explicitly asserts no image path/content ever appears in a log message.

## **Dependencies**

DT-1001, DT-1005.

## **Suggested commit message**

`feat(DT-1007): add pipeline/correction lifecycle logging`
