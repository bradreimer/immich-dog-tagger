# DT-1117: Sync silently omits classifications with no explanation

## **ID**

DT-1117

## **Related spec**

None -- bug fix, not new behavior. Reported as
[GitHub issue #11](https://github.com/bradreimer/immich-dog-tagger/issues/11).

## **Priority**

High

## **Status**

Completed

## **Goal**

When `Sync` produces fewer Immich albums than an operator expects, the reason must be visible
somewhere -- not silently absorbed. The reporter (also the project owner) manually reviewed and
classified at least 6 dogs & cats but only got 3 albums in Immich: "This should produce more, or
throw an error."

## **Context**

Two compounding bugs, both found by tracing exactly what happens between clicking "Sync" and the
job reporting done:

1. **`PipelineJobRunner._run()` always discarded the handler's final progress message.**
   Every job handler (`_scan_handler`, `_detect_handler`, `_classify_handler`,
   `_reclassify_handler`, `_sync_handler`) already calls `progress.message(...)` with an
   informative final status right before returning -- e.g. `_sync_handler` already computed
   `f"Synchronized {len(summary.identities)} identities"`. But `_run()` unconditionally called
   `self.service.complete_job(job, progress_message=f"{job.operation.value} completed")`
   immediately after, overwriting that message with a generic `"sync completed"` on every single
   job, of every operation, every time. This wasn't sync-specific -- `tests/test_job_runner.py`'s
   own `test_runner_executes_queued_job_and_marks_completed` asserted
   `job.progress_message == "scan completed"` despite the handler explicitly setting
   `message="Done"`, which is the bug encoded as a passing test.
2. **`SyncService.sync()` had no accounting for what it excluded.** Classifications are silently
   skipped when confidence is below `SyncPolicy.minimum_confidence` (0.80, hardcoded, never
   overridden by the real job path) or when `identity is None` and `include_unknown` is False
   (also hardcoded False) -- both by design, not bugs in themselves (this project's stance is "no
   manufactured confidence," so lowering the threshold to force more albums would be wrong). But
   there was no way to tell *how many* were skipped or *why*, so a legitimately-lower-than-expected
   album count and a real problem look identical from the operator's side. On top of that,
   `classification.crop.detection.asset.immich_asset_id` had no guard against a missing
   detection/asset -- one such row raised immediately while *building* the aggregation dict,
   before a single album had been touched, meaning one bad row could silently zero out an entire
   sync run (a job the operator likely never checked, since Overview's "Queued job #N" message
   never updates to reflect the job's actual outcome).

Together: sync could legitimately (by policy) or accidentally (one bad row) produce far fewer
albums than expected, and the one place that could have explained it -- the job's own status
message -- was being thrown away and replaced with a content-free "sync completed" regardless.

## **Implementation notes**

- `services/job_runner.py`: `complete_job(job, progress_message=job.progress_message or
  f"{job.operation.value} completed")` -- preserve the handler's last message; only fall back to
  the generic one if the handler never set one at all. Fixes this for every operation, not just
  sync.
- `services/sync.py`: `SyncSummary` gains `skipped_low_confidence`, `skipped_unknown`,
  `skipped_missing_asset` (all default 0, backward compatible). `sync()` counts each reason
  instead of just `continue`-ing silently, and the missing-detection/asset case is now a counted
  skip (`continue`) instead of an unguarded attribute access that could abort the whole run.
- `services/job_execution.py`'s `_sync_handler`: builds a final message like `"Synchronized 3
  identities (7 asset(s)); skipped 3 classification(s) (2 below confidence threshold, 1
  unidentified, 0 missing asset data)"` -- only appending the skip clause when something was
  actually skipped. Also returns the three skip counts in the job's result dict.
- `cli.py`'s `sync_command --dry-run` prints the same skip breakdown, for parity with the job path.

## **Acceptance criteria**

- A job's own final `progress_message` reflects what its handler actually reported, for every
  operation -- verified live against a running API instance (triggered `reclassify` on an empty
  database; `progress_message` read `"Reclassify pass 1: No labeled examples available; nothing to
  reclassify."`, not the old generic `"reclassify completed"`).
- After a sync that skips classifications, the job's completion message states how many were
  skipped and why (low confidence / unidentified / missing asset data).
- A classification with no resolvable detection/asset is skipped and counted, not left to abort
  the entire sync run.
- Existing sync behavior (which classifications produce which albums) is unchanged -- this is
  purely additive reporting, not a policy change.

## **Testing requirements**

- `tests/test_job_runner.py`: updated the existing test to assert the handler's own message
  survives completion; added a test confirming the generic fallback still applies when a handler
  sets no message at all.
- `tests/test_sync.py`: skip-counting tests for each of the three reasons independently, a
  combined "full accounting" test reproducing the issue's 6-classification scenario (3 sync, 2
  low-confidence, 1 unidentified) asserting the skip counts plus total always add back up to 6,
  and a regression test proving a missing-detection classification no longer aborts the whole
  sync.
- `tests/test_job_execution_sync.py` (new): `_sync_handler`'s final message includes the skip
  breakdown when something was skipped, and omits the clause entirely when nothing was.
- Full `./scripts/check.sh` passes.

## **Dependencies**

None.

## **Suggested commit message**

`fix(DT-1117): stop discarding job completion messages and report what sync skips`
