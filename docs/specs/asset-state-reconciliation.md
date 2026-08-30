# Asset State Reconciliation & Pipeline Self-Healing

## Purpose
Keep `state.db` (and the local cache/crop files it references) reconciled against reality --
both against Immich (assets get deleted there) and against the local filesystem (cached files
can go missing) -- so the review UI never shows stale content and a single broken record never
repeatedly fails an entire pipeline run.

## User Story
As a user who periodically deletes photos in Immich and runs the pipeline on a schedule, I want
the app to notice when a photo it knows about is gone and clean up after it, and I want a single
corrupted or missing local file to be repaired automatically the first time the pipeline hits it,
so that my review queue only shows real photos and a bad record doesn't keep failing my Full
Pipeline runs.

## Context
Two related classes of drift between `state.db` and reality currently have no repair path:

**1. Immich-side deletions are never reconciled.** `Scanner.scan()` only adds/updates `Asset`
rows from `ImmichClient.list_assets()` results; it never diffs against what's already in
`state.db`, so it has no way to notice an asset stopped appearing. There is no `DELETED`/removed
status on `Asset`, and the review query (`ReviewQueryService.active_review()`) and crop-serving
route (`GET /crops/{crop_id}`) both trust `state.db` and local disk without ever checking whether
the source asset still exists in Immich. Once scanned, an asset's row, cached original, and crops
live forever, even after the user deletes the photo in Immich -- which is why deleted photos keep
showing up for review.

**2. A missing local file fails the whole job, forever.** In a real run (job #111), `detect`
failed with `[Errno 2] No such file or directory` for one asset's cached original and the entire
Full Pipeline job was marked `FAILED`, 0/3 batches complete. Tracing this:
- `DetectionService.run()` has no per-asset isolation: `detector.detect(image_path)` raising
  any exception (including a missing file) is caught once, the whole in-progress batch is rolled
  back, and a `RuntimeError` is re-raised -- which propagates through `PipelineService.run()` and
  `services/job_execution.py` (neither of which catch anything) up to
  `PipelineJobRunner._run()`, the only place an exception is caught, at whole-job granularity.
- Because the exception fires before the asset's status is updated and before commit, the
  asset's status stays `DOWNLOADED`. A re-run's query selects it again and fails identically --
  an infinite loop the user already observed ("running it a second time shouldn't produce that
  error").
- `AssetStatus.DETECTION_FAILED` and `CLASSIFICATION_FAILED` are defined in `enums.py` but are
  never assigned anywhere in the codebase -- `detect`/`classify` have no failed-and-retryable
  path at all.
- `DerivedDataService.check()` (`check-derived-data`) already detects a `DOWNLOADED` asset with a
  missing cached file (`report.missing_downloads`), but only reports it; it never repairs
  anything, and its own printed guidance (re-run `download`) is insufficient, since plain
  `download` only re-fetches `PENDING`/`DOWNLOAD_FAILED` assets, not `DOWNLOADED` ones.
- The one place in the codebase that already solves this shape of problem is
  `Downloader._download_one()` (added per issue #99): it wraps each asset's download in its own
  try/except, flips that asset to `DOWNLOAD_FAILED` on failure, and lets the batch continue --
  and `download_pending()`'s query includes `DOWNLOAD_FAILED` so the very next `download` run
  retries it automatically. `detect` has no equivalent of either half of this pattern.
- `docs/status.md`'s Known Issues already flags this rough edge ("Detection/classification status
  ownership needs review"), and `storage-lifecycle-cleanup.md` confirms `detect`'s own original-
  deletion path is correctly ordered (commit-then-unlink) and not the cause of this -- the
  missing file is more likely from a `state.db` restore against a since-cleaned cache directory,
  or manual/out-of-band clearing of `cache_dir`. Regardless of root cause, the pipeline should not
  keep re-failing on it.

Both problems are the same shape: a local record has drifted from the reality it's supposed to
track (Immich, or the filesystem), and nothing closes the loop. This spec addresses both under
one reconciliation/self-healing capability, consistent with
[ADR-001](../adr/ADR-001-state-database-source-of-truth.md)'s framing of `state.db` as the
authoritative store that Immich and the local cache feed into and get synced back to.

## Goals
- Detect assets that have been deleted from Immich and reconcile them out of the active review
  queue and off disk, without silently destroying ground-truth review/learning history that has
  ongoing value.
- Give `detect` (and any other per-asset pipeline stage) the same per-asset error isolation
  `download` already has, so one bad asset can't fail an entire job when other assets in the same
  batch are healthy.
- Make a missing cached file for a `DOWNLOADED`/later asset self-repairing: the first time it's
  encountered, the affected asset is automatically routed back to a re-downloadable state instead
  of failing the same way on every subsequent run.
- Wire up `DETECTION_FAILED`/`CLASSIFICATION_FAILED` as real, visible, retryable states for
  failures that aren't a simple missing-file repair (e.g. a genuine decode error), mirroring how
  `DOWNLOAD_FAILED` already works.
- Give `check-derived-data` an actual repair action, not just a report.

## Non-goals
- A real-time or webhook-driven sync with Immich; reconciliation runs as part of existing
  scan/pipeline invocations, not a new standing background poller.
- Handling every conceivable corruption class (e.g. a file that exists but has truncated/corrupt
  bytes); scoped to "file is missing" and "asset no longer exists in Immich" for this pass.
- Changing backup/restore semantics -- `state.db`-only backups remain out of scope, though the
  interaction (a restored `state.db` can reference cache files a later cleanup already removed)
  is one of the mechanisms this spec's self-healing needs to cover gracefully, not fix at the
  source.
- Retrying indefinitely -- see Open Questions on bounding repair attempts.

## Requirements

### Immich deletion reconciliation
- **FR-1**: During `scan` (or a dedicated reconciliation pass within it), determine which
  previously-known, still-active assets are no longer returned by Immich, using whatever
  mechanism Immich's API supports most cheaply (existence check, trash/deleted-assets endpoint,
  or diffing the current scan's result set against previously-scanned assets) -- see Open
  Questions.
- **FR-2**: A confirmed-deleted asset is moved to a terminal, non-active status (e.g. a new
  `AssetStatus.REMOVED`) rather than being hard-deleted from `state.db` outright, so provenance
  and any downstream history referencing it remain queryable.
- **FR-3**: `ReviewQueryService.active_review()` and any other queries that surface assets for
  human action exclude assets in the removed state.
- **FR-4**: The asset's cached original and crop files are deleted from disk once it's marked
  removed, unless FR-5 requires retention.
- **FR-5**: If a removed asset's crops are in active use as embedding examples / active-learning
  reference material, they are retained (or the decision to retain vs. delete is made explicit
  per the Open Question below) rather than silently destroyed as a side effect of cleanup.
- **FR-6**: Immich sync (`services/sync.py`) does not attempt to add/maintain album membership
  for a removed asset.

### Pipeline self-healing
- **FR-7**: `DetectionService.run()` isolates per-asset failures: an exception raised while
  processing one asset is caught, logged, and does not abort the rest of the batch or the job,
  mirroring `Downloader._download_one()`.
- **FR-8**: When the per-asset failure is specifically a missing cached original file, the asset
  is automatically routed back to `AssetStatus.DOWNLOAD_FAILED` (or `PENDING`) rather than being
  left at `DOWNLOADED` -- so the pipeline's own next `download` batch (within the same Full
  Pipeline run, since `download` runs before `detect` each iteration) or the next standalone
  `detect` invocation re-fetches and reprocesses it instead of failing identically again.
- **FR-9**: A per-asset failure that isn't a missing-file case (e.g. a genuine decode/detector
  error) is routed to `AssetStatus.DETECTION_FAILED` instead, logged with enough detail to
  diagnose, and counted/surfaced (the existing but currently-dead counters in
  `services/status.py` and `services/metrics.py` become live).
- **FR-10**: The equivalent isolation/repair/failed-status handling is applied to `classify`
  (`CLASSIFICATION_FAILED`) for the same class of missing-input failure (e.g. a missing crop
  file), for consistency -- not just `detect`.
- **FR-11**: A Full Pipeline job whose batches contain a mix of successes and per-asset failures
  completes as a partial success (with a count of repaired/failed items surfaced), rather than
  the whole job being marked `FAILED` because of one bad record.
- **FR-12**: `DerivedDataService` gains a repair action (e.g. `check-derived-data --repair`, or a
  new command) that, for each `DOWNLOADED`/later asset with a missing expected file, applies the
  same repair routing as FR-8 -- turning today's report-only guidance into something that
  actually fixes the gap.

## Acceptance Criteria
- Deleting a photo in Immich and then running `scan` (or a Full Pipeline run) causes that asset
  to disappear from the active review queue and its cached original/crop files to be removed
  from disk (or explicitly retained per FR-5's resolution) within that run.
- Re-running the exact scenario from job #111 (a `DOWNLOADED` asset whose cached file is missing)
  no longer fails the job: the first run repairs the asset (re-download, then successful detect)
  and does not require manual intervention or a second identical failure.
- A single asset with a genuine (non-missing-file) detection error no longer fails an entire Full
  Pipeline job; other assets in the same batch/job still complete, and the failed asset is
  visible as `DETECTION_FAILED` with a retry path.
- `check-derived-data --repair` (or equivalent) turns previously-reported `missing_downloads` /
  missing crop entries into zero on a subsequent `check-derived-data` run, without requiring
  `download --force` over the whole library.
- No existing reviewed classification, dog identity, or (pending FR-5's resolution) actively-used
  embedding example is silently destroyed as a side effect of Immich-deletion cleanup.

## Open Questions
- Does Immich's API expose a way to check single-asset existence or list trashed/deleted assets
  directly, or must FR-1 be implemented by diffing successive `list_assets()` result sets against
  `state.db`? This should be confirmed against the Immich API before implementation stories are
  written.
- Should a removed asset's crops that are in use as active-learning embedding examples be
  retained indefinitely, retained with a "source deleted" marker, or deleted along with
  everything else on the theory that a human deleted the photo intentionally? This has real
  active-learning-quality implications (per
  [ADR-002](../adr/ADR-002-active-learning-architecture.md)) and needs a product decision, not
  just an engineering default.
- How many times should FR-8's automatic repair retry before giving up and surfacing a permanent,
  human-actionable failure, so a fundamentally broken disk/mount doesn't spin forever
  re-attempting the same download?
- Should the Jobs UI change to represent "completed with N repaired / N failed" distinctly from
  today's binary succeeded/failed, to surface FR-11's partial-success outcome to the user?
- Is `AssetStatus.REMOVED` (FR-2) the right terminal state, or should this instead be a boolean
  soft-delete flag alongside the existing status, to avoid colliding with status-driven logic
  elsewhere that switches on `AssetStatus`?
