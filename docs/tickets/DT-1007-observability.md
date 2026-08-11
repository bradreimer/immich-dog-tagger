# TICKET 07: Logging and operational diagnostics

## Status
Completed

## Implementation notes
- `services/job_runner.py::PipelineJobRunner._run()` now logs start (job id, operation), successful completion (duration), and failure (duration, error message) for every `PipelineOperation` -- this covers the whole pipeline/reclassification lifecycle from one place rather than requiring each handler to log separately.
- `ClassificationService.classify()` logs stage/mode and resulting counts (classified, unknown) -- counts only, no crop paths.
- `ClassificationCorrectionService.correct()` logs `classification_id`, previous identity, and new identity -- explicitly never the crop's file path (regression-tested).
- Reclassify already had start/complete/failure logging with counts and duration from DT-1001; `job_recovery.py` already logs startup reconciliation counts from DT-1005.
- Stale vs. active job/pass distinction: DT-1005's recovery reconciliation plus these lifecycle logs mean a stuck job/pass has both a log trail (last successful tick) and a DB status (`FAILED` with an explanatory `error_message`) rather than an ambiguous `RUNNING` with no context.
- UI already surfaces actionable errors: the diagnostics "Recent failures" card (pre-existing) and the new Learning Progress "Last Reclassify: Failed" state (DT-1006).
- Tests: `tests/test_logging.py` asserts logs are emitted on both the success and failure paths and explicitly asserts no image path/content ever appears in a log message.

## Goal
Make failures diagnosable without exposing sensitive data.

## Steps
1. Add structured logs for pipeline/reclassification lifecycle.
2. Log counts, durations, identifiers, and stage names, not image contents or secrets.
3. Surface actionable errors in the UI.
4. Add enough context to distinguish stale jobs from active jobs.
5. Verify logs at normal and failure paths.

## Done when
A failed reclassification can be diagnosed from application logs and UI status without inspecting source code.
