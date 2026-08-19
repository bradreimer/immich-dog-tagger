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
- #94 v1.6.0 Pet Insights: a new `PetOccurrence` fact table, materialized as a side effect of AUTO
  classification/review correction/reclassification settling an identity for a crop; `Asset`
  gained cached location/people/favorite fields sourced from the same Immich response the scanner
  already fetches; `InsightsService` computes summary/timeline/places/people at read time
  (never stored as a conclusion -- see [ADR-004](adr/ADR-004-pet-occurrence-observations.md));
  read-only `GET /api/dogs/{id}/insights/*` endpoints; a per-dog Insights page in the UI; and
  `immich-dog-tagger backfill-occurrences` for existing libraries. See
  [docs/specs/v1.6-pet-insights.md](specs/v1.6-pet-insights.md).
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
- #107 fixed a follow-up to #104: batching `detect`/`classify` commits and adding a 30-second
  `busy_timeout` shrank the write-lock window but didn't remove it -- a full pipeline run's
  `Downloader.download_pending()` and `ClassificationService.classify()` still hold an implicit
  read transaction open across a whole batch of slow per-item work (an HTTP download, an embedding
  pass), and that window can exceed 30 seconds, so a concurrent write (e.g. creating a dog/cat from
  the UI) still failed with `database is locked`. `create_database()` now sets `state.db` to
  SQLite's WAL journal mode (plus its recommended `synchronous=NORMAL` companion) via a
  `sqlalchemy` `"connect"` event listener, so readers and a writer can proceed concurrently instead
  of contending for the same single lock; the existing `busy_timeout` remains as the safety net for
  writer-vs-writer contention.
- #110 v1.7.0 Pluginable Insight Providers: `InsightProvider` protocol + explicit
  `INSIGHT_PROVIDERS` registry (`services/insights/providers.py`); `services/insights.py` split
  into a package (`aggregations.py`, `providers.py`, `service.py`), with the favourite-place/
  favourite-human/Immich-favorite-count logic previously inline in `InsightsService.summary()`
  reorganized onto shared aggregation helpers the providers also use -- a behavior-preserving
  refactor, `InsightsService.summary()`'s signature and response shape unchanged; new read-only
  `GET /api/dogs/{id}/insights/cards` endpoint and a `DogInsightsPage` card grid rendering
  whatever's registered, so future providers need no endpoint or frontend change; a first new
  provider landed as proof, `TotalPhotosMilestoneProvider` (a round-number confirmed-photo-count
  Milestone, e.g. "1000th confirmed photo"). See
  [docs/specs/v1.7-pluginable-insights.md](specs/v1.7-pluginable-insights.md) and
  [ADR-005](adr/ADR-005-insight-provider-plugin-architecture.md).
- #111 cancel a running pipeline job: the Job Queue's Cancel action previously only worked on a
  `PENDING` job (`PipelineJobService.cancel_job()` rejected anything else), and no Cancel button
  existed in the UI at all, for any status. `PipelineJob` gained a `cancel_requested` flag (status
  stays `RUNNING` while a cancellation is pending, not a new status value, so `has_running_job()`/
  the dispatcher/the scheduler need no changes); `cancel_job()` now sets it for a `RUNNING` job via
  an atomic `UPDATE ... WHERE status='RUNNING'` (closing a TOCTOU race against the job finishing
  concurrently) for the operations with an incremental commit checkpoint to roll back to --
  scan/detect/classify/full_pipeline; `embed`/`learn`/`sync` have no partial checkpoint to preserve
  and stay `PENDING`-only, same as before. A `should_cancel` callable is threaded down to each
  service's existing batch-commit checkpoint; on a hit, the uncommitted slice since the last commit
  is rolled back and only the already-committed counts are kept, and `PipelineJobRunner._run()`
  finalizes the job as `CANCELED` (a new `finish_canceled_job()`, not `complete_job()`) once its
  handler returns having honored the flag. `DetectionService`/`ClassificationService`'s
  commit-checkpoint size is also reduced (1000/500 -> 50/25): SQLite allows only one writer at a
  time even under #107's WAL mode, and a GPU/CPU-bound batch that large could hold that lock for
  minutes, well past a concurrent Cancel click's 30-second `busy_timeout` budget.
  `ClassificationService.classify()` is also restructured to select/embed/commit in internal
  chunks rather than embedding its whole selection up front, so an unlimited standalone Classify
  job has a cancellation checkpoint at all. Also fixed alongside this: `DetectionService` deleted
  each asset's cached original file immediately per-asset, before that asset's batch committed --
  a cancellation (or any mid-batch failure) rolling back the tail of a batch could leave an asset
  reverted to `DOWNLOADED` with its cache file already gone, permanently stuck since
  `download_pending()` only re-fetches `PENDING`/`DOWNLOAD_FAILED` assets; the unlink is now
  deferred until the batch actually commits.
- #117 highlight the predicted identity button on the review page: `item.prediction.identity` is
  now threaded through `ReviewCard` -> `ReviewActions` -> `IdentityChooser`, and the
  `IdentityChooser` button matching the prediction renders with the app's existing filled
  (`default`) button variant plus a star icon, while the rest use `outline` -- the same
  selected/unselected visual language already used for the review queue's filter buttons, so no
  new accent color was introduced.

- [#116](https://github.com/bradreimer/immich-dog-tagger/issues/116) explicit dog/cat species
  correction on the Review page: YOLO occasionally mixes up dogs and cats, and `Crop.species` was
  previously set once at crop-creation time with no way to fix it afterward. New
  `POST /classifications/{id}/species` endpoint and
  `ClassificationCorrectionService.correct_species()` rescore the crop's already-stored embedding
  against the corrected species' reference pool via `IdentityClassifier` (no re-download/
  re-embedding), forget any stale learning example filed under the wrong species
  (`Learner.forget_image`), and deliberately write no `ReviewAction` -- a species change doesn't
  decide an identity, so recording one would make `ReviewQueryService.review_queue_count()` treat
  the item as already reviewed and drop it from the active queue while still effectively
  unclassified. Also fixed a latent inconsistency this feature would otherwise have exposed:
  `services/metrics.py`'s per-species Learning Progress breakdown grouped by `Detection.label`
  (the detector's raw, possibly-wrong output) instead of `Crop.species` (the corrected,
  authoritative value) -- the two always matched before this feature existed, so it was invisible
  until species became correctable. Review page gained two distinctly colored "Dog"/"Cat" buttons
  (reusing the existing validated categorical chart palette, not new colors) alongside the
  existing identity chooser. See
  [docs/specs/species-correction.md](specs/species-correction.md).

- [#125](https://github.com/bradreimer/immich-dog-tagger/issues/125) show the running app version
  in the sidebar footer and on the Settings page, so a maintainer can tell what release they're on
  without checking `pyproject.toml` or a container tag. Added
  `immich_dog_tagger.version.get_version()` (reads installed package metadata via
  `importlib.metadata`) as the single source of truth, replacing the separate hardcoded
  `version="1.6.0"` literal previously passed to the `FastAPI(...)` constructor. Surfaced via the
  existing `/health` response (sidebar, fetched once on mount) and a new `version` field on
  `SettingsResponse` (Settings page's existing `/settings` fetch). Also added `afterEach(cleanup)`
  to the Vitest setup, a latent gap from the framework's initial setup that only surfaced once a
  test file asserted DOM uniqueness/absence across multiple tests.

- [#128](https://github.com/bradreimer/immich-dog-tagger/issues/128) "View in Immich" link on the
  Review page, on the same line as the review-reason badge and the capture date, so an ambiguous
  crop can be checked against the full original photo without leaving the app to hunt for it by
  date. `ReviewItem`/`ReviewItemResponse` now carry the crop's `immich_asset_id` (read from the
  already-eager-loaded Crop -> Detection -> Asset chain, so no extra query), and the link is built
  client-side by `immichAssetUrl()` from the `immich_url` the Settings endpoint already exposes --
  no image data or metadata leaves the local deployment. Fails open the same way `captured_at`
  does: no configured Immich URL or no asset behind the crop simply renders no link.

- [#129](https://github.com/bradreimer/immich-dog-tagger/issues/129) fixed the Insights page's
  "Most photographed place" and "Most often photographed with" tiles (and the Places/People
  cards) always being blank: `ImmichClient.list_assets()` posted to
  `/api/search/metadata` without `withExif`/`withPeople`, which Immich gates `exifInfo` and
  `people` behind, so every asset parsed to `latitude=None`/`city=None`/`people=()` and the
  location/people cache #94 added to `Asset` never held anything. `isFavorite` (a top-level,
  ungated field) worked throughout, which is why only the place/person facts were affected. No
  schema change: existing libraries pick the data up on their next `scan`, which already refreshes
  cached location/people/favorite for assets it has seen before.
- #132 browser-facing Immich URL split out from the API URL: `IMMICH_URL` was doing double duty
  as both the address the backend calls Immich at and the base for the "View in Immich" deep link
  handed to the browser (#130), so a Docker-internal `IMMICH_URL` produced a link the reviewer's
  browser couldn't resolve. New optional `IMMICH_EXTERNAL_URL` supplies the browser-facing base and
  falls back to `IMMICH_URL` when unset, so single-address deployments are unchanged;
  `GET /api/settings` now returns both and the Settings page shows them separately

- [#134](https://github.com/bradreimer/immich-dog-tagger/issues/134) fixed the Overview tab warning
  "1 stuck job(s) -- manual recovery may be required." for every job the moment it was started:
  `GET /diagnostics` classified *any* `RUNNING`/`PENDING` job as stuck, with no staleness test at
  all, so the warning fired on healthy work and cleared only when the job finished. `PipelineJob`
  gained a `heartbeat_at` liveness column (additive migration, left NULL for existing rows so a
  job's real age survives via `last_activity_at`'s `started_at`/`created_at` fallback), stamped
  when a job starts and refreshed by every progress report -- the job's own commit checkpoints,
  never an extra mid-batch write a service might still roll back. A new
  `job_recovery.find_stuck_jobs()` reports only jobs idle past `STUCK_JOB_IDLE_THRESHOLD` (1 hour),
  and never a `PENDING` job queued behind a `RUNNING` one, which is just waiting its turn; the
  Overview warning now names the threshold and each job's idle time instead of asserting
  stuckness. Fixed alongside it: `services/job_dispatcher.py` carried a Python 2
  `except RuntimeError, ValueError:` clause -- a `SyntaxError` that took down the whole FastAPI app,
  since `api/dependencies.py` imports the dispatcher at import time.

- [#137](https://github.com/bradreimer/immich-dog-tagger/issues/137) fixed crops being rotated and
  cut from the wrong region of the photo: the detector and the crop writer decoded the same file
  into two different coordinate spaces. Pillow ignores the EXIF `Orientation` tag (274) and returns
  the raw stored pixels, while ultralytics decodes a path through OpenCV, which applies it -- so
  for any photo not tagged `Orientation=1` (most phone photos), YOLO returned boxes in the upright
  frame and `CropWriter` applied them to the unrotated buffer. Rotation was the visible symptom;
  the crop also came from the wrong part of the photo, and `OpenClipEmbedder` embedded the result
  into the learned reference set. This is also the root cause of the out-of-bounds detection boxes
  in #88 -- a swapped width/height is exactly what produced them, and #88's clamping treated the
  symptom. New `images.open_upright()` is now the single decoding path for detection, cropping, and
  embedding: it applies `ImageOps.exif_transpose` (all eight orientations, including the mirrored
  2/4/5/7) and registers the `pi-heif` opener, which nothing in `src/` did -- HEIC decoding had
  been working only because ultralytics monkeypatches `PIL.Image.open` globally. `YOLODetector`
  now decodes through it and passes the image to `model.predict()` rather than handing over a
  path, so detector and cropper agree for every supported format including the HEIC fallback path,
  where ultralytics uses Pillow and would otherwise have disagreed. Existing crops and embeddings
  are deliberately not rewritten; the remediation path is documented in docs/workflow.md section 7
- #140 v1.8.0 FR-1 Library scoped to one pet: the Library's species and identity filters became a
  selection step -- a species chooser (Dogs / Cats / All species) plus a pet chooser listing the
  active identities -- backed by a `LibraryWorkspaceProvider` context so the clustering, sorting,
  and approval stories under #139 read the same selection rather than a filter row's local state.
  Changing species clears a pet that no longer applies (no stale dog selected under Cats), every
  selection change still resets pagination, the flat "all photos" view keeps its review-status and
  capture-date filters and pagination unchanged, and a library with no identities configured points
  the owner at Dogs & Cats instead of showing a blank chooser. No API change: `GET /api/library`
  already accepted `identity` and `species`. See
  [docs/specs/v1.8-library-approval-workspace.md](specs/v1.8-library-approval-workspace.md).
- #146 v1.8.0 FR-8 detection coverage on the Metrics tab: a new **Library Coverage** card whose
  denominator is photos detection has finished with, not the crops it produced -- so photos that
  yielded no crop (the population a missed pet hides in), photos awaiting detection, and photos that
  could not be processed are each visible as their own count instead of being absent from every
  existing figure. Two fixed aggregate queries, pinned by a query-count assertion on the endpoint;
  the existing automation-rate/confident-coverage definitions are unchanged and pinned by a
  regression test. Deliberately labeled coverage, never accuracy or recall -- there is no ground
  truth for photos detection never flagged. See
  [docs/specs/v1.8-library-approval-workspace.md](specs/v1.8-library-approval-workspace.md).
- #148 merge two identities (v1.8 FR-10): `DogService.merge_dogs()` absorbs one identity into
  another -- every `CropClassification` naming the source (scoped to crops of the merged species,
  since `identity` is a bare name and names are unique per species) is re-pointed at the target,
  the source's `EmbeddingExample` rows are re-filed onto it (dropping any whose crop path the
  target already holds, the same one-animal-per-crop invariant `Learner` maintains), and its
  `PetOccurrence` rows follow. `ReviewAction` history is deliberately not rewritten: a merge
  re-attributes derived state, not the record of who decided what. Cross-species merges are
  rejected outright (DT-1110's dog-"Max"/cat-"Max" distinction). The source is left as a
  deactivated tombstone rather than deleted, and the merge itself is recorded in a new
  `identity_merges` provenance table, since a bulk re-attribution can't be read back off the rows
  it touched. Writes commit in bounded batches (the #104/#107 lock-contention class of bug), and
  Immich albums reconcile on the next sync through the existing DT-1113 `SyncedAsset` stale-
  membership diff -- the merge deliberately leaves those rows alone so sync can see them as stale.
  New `POST /dogs/{id}/merge` and a two-step, destructive-styled, confirmed merge control on the
  Dogs & Cats page

## Current Milestone
v1.8.0 Library as an approval workspace ([#139](https://github.com/bradreimer/immich-dog-tagger/issues/139),
[docs/specs/v1.8-library-approval-workspace.md](specs/v1.8-library-approval-workspace.md)) is in
progress: FR-1 (#140, species -> pet selection as the Library's primary axis), FR-8 (#146,
detection coverage) and FR-10 (#148, merging two identities) have landed; clustering and cluster
approval (#141), in-cluster selection (#142), sorting (#143), rejection (#144), and cold start
(#145) are still open, as are the remaining supporting gaps #147 and #149.

Previously: no queued numbered milestone. v1.7.0 Pluginable Insight Providers (#110) shipped and is recorded
as completed in [docs/roadmap.md](roadmap.md); #111 (cancel a running job), #116/#117 (review
page species correction, predicted-identity highlight), and #125 (version display) followed as
additional reliability/UX fixes, along with #128 (link from a review item to its original photo
in Immich). `pyproject.toml`/`uv.lock`/the API app version had lagged at 1.6.0 through all of
that; this catches them up to 1.7.0 and tags the release.

## Next Work
Next under v1.8.0: #141 (cluster recommendations for the selected pet and approve a cluster in one
action), which depends on #140 and on settling the spec's first open question -- which clustering
algorithm, and whether it runs on demand or as a job with cached assignments.

Otherwise, v1.7.0's own explicitly-deferred items (see spec Non-goals): On This Day, Best Friends (pet-to-pet
co-occurrence), and a Pet World Tour map -- each becomes a new provider under the architecture
#110 landed, not a core change. Otherwise: improved reference-example selection, reference-set
curation workflows, and confidence analysis (see docs/roadmap.md "Active Learning Improvements"),
v1.5's own open questions (owner-tunable decay scale/floor, reporting how many reclassified items
changed identity specifically due to temporal weighting), or extending #111's cancel-while-running
support to `reclassify` (already batches the same way; deliberately left out of #111 to keep that
change smaller).

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
