# Current Status

## Completed
- Detection pipeline
- Classification pipeline
- Review queue API
- React review interface
- Correction workflow
- Skip workflow
- Review action tracking
- API hardening and review service-boundary cleanup
- Learning and review statistics
- DT-0901 through DT-0944 (job system, scheduling, backup/recovery, production validation, dynamic dog management -- v0.9.0 through v0.9.4)
- DT-1000 v1.0.0 architecture audit
- DT-1004 centralized nearest-neighbor classifier policy
- DT-1001 reclassification service/job
- DT-1003 review-to-example ground-truth hardening (fixed a real leakage defect)
- DT-1005 job lifecycle/idempotency/recovery for Reclassify
- DT-1002 + DT-1006 Reclassify action and Learning Progress dashboard
- DT-1007 pipeline/correction lifecycle logging
- DT-1008 scale validation (fixed two N+1 defects; documented gap: no literal 30k-image run performed in this environment)
- DT-1009 end-to-end review-driven learning loop test suite
- DT-1010 v1.0 user and operator documentation (docs/workflow.md)
- DT-1011 v1.0.0 release validation (see docs/validation/v1.0.0/DT-1011-release-validation.md)
- DT-1103 dedicated Metrics tab, next to Mission Control
- DT-1101 per-pass labeled-example-count/review-queue-size snapshots
- DT-1102 reconciled review-queue metric and prominent automation-rate metric
- DT-1104 visual style foundations: blue accent tokens, validated status/categorical palette,
  sidebar navigation shell, stat-tile primitive
- DT-1105 rolled the visual style out to all four pages, including Metrics' donut and trend
  charts
- DT-1106 UX review follow-ups: destructive-button contrast fix, relative "last updated" time,
  Mission Control next-action banner, Metrics automation trend delta
- DT-1107 moved dog management to its own `/dogs` page and sidebar tab
- DT-1108 consolidated Metrics' trend section into one dual-axis Progress Over Time chart
- DT-1109 fixed a 500 on `POST /classifications/{id}/correct` (raw ORM object with a binary
  embedding column was reaching FastAPI's JSON encoder)
- DT-1110 cat support alongside dogs: species-scoped identities and crops, species-scoped
  nearest-neighbor classification, unified dog+cat review queue with per-item species-scoped
  identity chooser, species-aware Immich album naming (also fixed a same-name-cross-species
  album-collision bug in `SyncService.sync()`), per-species Learning Progress breakdown, and a
  backward-compatible additive migration for existing dog-only projects
- DT-1111 show each photo's own capture date next to its prediction/confidence everywhere a
  classification is shown (Review page and the review export text), plumbed through
  Crop -> Detection -> Asset with no N+1 query regression
- DT-1112 searchable, paginated Library page (new `/library` route and sidebar tab) showing every
  classified photo, reviewed and unreviewed alike, filterable by identity/species/reviewed-status/
  capture-date range -- the existing `/review` queue is unchanged
- DT-1113 identity correction control on each Library entry (reuses the existing
  `POST /classifications/{id}/correct` endpoint), plus the real fix underneath it: a new
  `SyncedAsset` table tracks each asset's last-synced `(species, identity)` membership so
  `SyncService.sync()` can detect and remove stale Immich album membership after a correction --
  previously an asset corrected from one identity to another stayed in both albums forever, since
  `sync_identity()` only ever added
- DT-1115 fixed a production bug: `review_queue_stats().remaining` (behind the Mission Control
  banner and sidebar "Review" badge) counted every unreviewed classification including
  confidently-classified ones, so it could claim "N images need review" while the actual `/review`
  queue was empty -- it now reuses `review_queue_count()`, the same definition `/metrics` already
  used, so `remaining` matches what `/review` actually returns everywhere it's surfaced
- DT-1114 date-aware classification: `IdentityClassifier.classify()` takes the crop's own capture
  date and flags (never silently excludes) a candidate whose match falls outside that identity's
  optional owner-set active date range (`Identity.active_from`/`active_until`, editable from the
  Dogs & Cats page via a new `set_active_range`/`PUT /dogs/{id}/active-range`), surfaced as a new
  `date-conflict` review/library reason; fails open with zero behavior change for crops with no
  capture date or identities with no range set (**superseded by v1.5, see below**)
- DT-1116 fixed [GitHub issue #12](https://github.com/bradreimer/immich-dog-tagger/issues/12):
  "Clear list" in Job Queue > History only cleared frontend state, so a refresh brought every job
  straight back -- `PipelineJob` gained a `visible` flag, `POST /jobs/clear-history` hides
  (never deletes) finished jobs server-side, and `GET /jobs` excludes them by default; pending/
  running jobs are never hidden
- DT-1117 fixed [GitHub issue #11](https://github.com/bradreimer/immich-dog-tagger/issues/11):
  Sync producing fewer Immich albums than expected had no explanation anywhere -- `PipelineJobRunner`
  was discarding every job's own final status message (not sync-specific; affected every
  operation) in favor of a generic "\<operation\> completed", and `SyncService.sync()` had no
  accounting for classifications it skipped (low confidence / unidentified / a missing
  detection-asset chain that could previously abort an entire sync run on one bad row). Job
  completion messages now survive, and a sync that skips anything says how many and why.
- DT-1118 fixed a production-blocking bug found while preparing for a first full-library scan:
  `ImmichClient.list_assets()` called Immich's paginated `/api/search/metadata` endpoint exactly
  once and never followed its `nextPage` cursor, so `scan` silently discovered only the first 1000
  assets in any library and stopped -- no error, no warning. It now loops until `nextPage` is
  exhausted, so a full scan sees the entire library regardless of size; single-page libraries are
  unaffected.

- #99 fixed scan/download stability: `Scanner.scan()` and `Downloader.download_pending()` each
  called `session.commit()` exactly once, after processing every asset in the run, so a failure
  anywhere in a large run discarded all progress back to the run's start. Both now commit every
  1000 assets (rolling back and re-raising with the failing asset id and how many were already
  committed if a batch commit itself fails), so a mid-run failure leaves fewer than 1000 assets to
  redo -- the next scan/download retries only those. `Downloader` also widened its per-asset error
  handling from `ImmichDownloadError` only to any unexpected exception (disk I/O, unwrapped
  network errors), so one bad asset no longer aborts the rest of the batch. Follow-up: a plain
  (non-force) `download_pending()` now also retries `DOWNLOAD_FAILED` assets, not just `PENDING`
  ones -- previously a transient failure (e.g. a timeout) left an asset stuck forever unless
  someone remembered to pass `--force`, which redownloads everything rather than just what's
  missing.
- #103 batched full-pipeline runs: `PipelineService.run()` (the `full_pipeline` job driving "run
  pipeline") now downloads/detects/classifies in chunks of 1000 assets rather than running each
  stage to completion across the entire library before the next starts, so a first-time run
  against a large library produces reviewable crops after the first ~1000 assets instead of only
  once everything has finished (`force=True` reprocessing still runs as a single unbatched pass,
  since its query has no status filter to advance through on repeated calls). Each completed batch
  now also logs a `Full pipeline batch N complete: count/total asset(s) processed this run` line
  via the standard logger; fixed alongside this that INFO-level `logger.info(...)` calls
  throughout the app (this one and pre-existing ones in scanner/downloader/classification/
  scheduler) were being silently dropped everywhere -- neither `api/app.py` (served via uvicorn
  per `docker-compose.yml`) nor `cli.py`'s `main()` configured a root logging handler, so nothing
  below WARNING ever reached `docker logs`. Both now call `logging.basicConfig(level=logging.INFO)`
  on startup.
- #83 Settings tab showing the configured Immich URL and scanned-image count (read-only;
  `GET /api/settings` never returns `immich_api_key`)
- #91 v1.5.0 automatic temporal-recency classification: removed DT-1114's manual owner-set
  `Identity.active_from`/`active_until` range entirely (schema, API, Dogs & Cats page UI) and
  replaced it with continuous per-example weighting -- `SimilarityScorer` scores each candidate
  example by how closely its own `captured_at` aligns with the photo being classified (Gaussian
  decay, ~1 year scale, fail-open on a missing date, floor so a lone identity's old examples still
  win with nothing closer-in-time to compete against), and `IdentityClassifier` ranks/selects by
  that weighted score while still reporting each winning match's true, unweighted cosine
  similarity as confidence. The `date-conflict` review/library reason is now `temporal-mismatch`.
  See [docs/specs/v1.5-automatic-temporal-classification.md](specs/v1.5-automatic-temporal-classification.md)
  and [ADR-003](adr/ADR-003-automatic-temporal-recency-classification.md).
- #104 fixed `detect`/`classify` holding state.db's write lock for the duration of the entire run:
  `DetectionService.run()` and `ClassificationService.classify()` each committed exactly once,
  after processing every eligible asset/crop, so a large run (minutes of YOLO inference or
  embedding+classification work) blocked every other reader -- the API's review/jobs/schedules
  endpoints and the background scheduler tick -- with an immediate `database is locked` error for
  as long as it ran. Both now commit every batch (1000 assets for detect, 500 crops for classify,
  matching scanner/downloader's existing #99 convention and PetOccurrenceService.sync_all's
  existing batch size respectively), rolling back and re-raising if a batch fails so a mid-run
  failure -- and the caller's own failure-status commit, which shares the same session -- can't
  silently persist a still-uncommitted straggler batch. The SQLite engine also now sets a
  30-second `busy_timeout`, so any connection that does land on a brief lock window waits for it
  to clear instead of failing instantly.

## Current Milestone
v1.6.0 Pet Insights -- in progress (issue #94). A read-only "fun layer" on top of confirmed pet
identifications: per-dog photo counts, date range, most-common places, and most-often-photographed
-with people, derived at read time from a new `PetOccurrence` fact table (never stored as a
conclusion -- see [ADR-004](adr/ADR-004-pet-occurrence-observations.md)). See
[docs/specs/v1.6-pet-insights.md](specs/v1.6-pet-insights.md).

## Next Work
v1.6.0's own explicitly-deferred items (see spec Non-goals): Best Friends (pet-to-pet
co-occurrence), On This Day, a Pet World Tour map, and Milestones. Otherwise: improved
reference-example selection, reference-set curation workflows, and confidence analysis (see
docs/roadmap.md "Active Learning Improvements"), or v1.5's own open questions (owner-tunable decay
scale/floor, reporting how many reclassified items changed identity specifically due to temporal
weighting).

## Workflow Notes
- New features should begin with a spec in docs/specs/.
- Implementation-sized work should be captured as a GitHub Issue (see the "User Story" or "Bug
  Report" issue templates; use "Feature Request" for an unscoped idea first).
- Documentation should be updated alongside code changes.

## Known Issues
- Some pipeline status counters may need future cleanup.
- Detection/classification status ownership needs review.
- Endpoint-level API auth is not implemented yet.
- DT-1008's scale validation used synthetic-scale regression tests rather than a literal 30,000-real-image run (no GPU/Immich instance in the development environment); a real-library run is recommended before relying on it at that scale in production.
