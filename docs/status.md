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
- #141 cluster recommendations and approve a cluster in one action (v1.8 FR-2/FR-3): the Library's
  selected pet now gets its pending recommendations grouped into clusters of visually similar crops,
  each approvable in one click. `RecommendationClusterService` pools the unreviewed classifications
  where the pet is the accepted identity *or* a stored candidate, and groups them with
  agglomerative average-linkage clustering over cosine distance (new `clustering.py`), computed on
  demand -- a read that writes nothing, proposes groupings only, and never touches `policy.py`'s
  thresholds. Each cluster reports a representative crop (the medoid), member count, confidence
  range (the *pet's* similarity, not the top candidate's) and capture-date range; crops with no
  stored embedding are reported as excluded rather than crashing the pass; the pool is capped at 500
  and says when it capped. `ClusterApprovalService` applies an approval as N ordinary corrections
  through `ClassificationCorrectionService.correct()` -- same `ReviewAction` rows, same
  `EmbeddingExample` provenance, same next-sync album reconciliation (DT-1113) -- committing in
  batches of 25 so a mid-approval failure leaves committed progress, and reporting applied/skipped
  counts with a reason per skip (DT-1117's accounting convention). Approving changes no Immich
  state; albums reconcile on the next operator-triggered sync (ADR-006). New
  `GET /library/clusters` and `POST /library/clusters/approve`, and a Recommendations panel on the
  Library page
- #142 per-photo selection within a recommendation cluster (v1.8 FR-4): a cluster is no longer
  all-or-nothing. Every member is a toggle, members start selected (deselecting the odd photo out
  is the exception path, so the common case stays one click), select-all/select-none and a
  "N of M selected" count sit beside the approve control, and the control names what it will apply
  to ("Approve 14 photos") instead of just "Approve". Deselecting everything disables approve, and
  an empty list is refused by both the schema and `ClusterApprovalService` rather than read as
  "approve the cluster". The approval submits the explicit selected ids and the server never
  re-derives membership from them -- and it now validates each id against the same pool rule that
  produced the cluster, so an id the classifier never proposed this pet for is skipped as
  `not-recommended` rather than silently labelled (the boundary check a stale page or a
  hand-written request has to hit). The selection itself is a generic `useSelection` hook outside
  the Library feature: this is the app's first multi-select, the flat library grid is the next
  caller, and it stores *deselections* so a list that grows keeps its new members selected and a
  changed list resets rather than carrying a stale selection across pets. No new keyboard
  vocabulary -- members are real toggle controls, so `useReviewKeyboard.ts` stays the app's only
  keymap
- #143 sort clusters and photos by capture date or confidence (v1.8 FR-5): `RecommendationCluster
  Service.clusters()` takes a `sort` (`captured_asc`, `captured_desc`, `confidence_desc` --
  default, `confidence_asc`) that orders both the cluster list and each cluster's members from the
  data already eager-loaded for review/library items -- no per-row lookup, no added query
  regardless of pool size. A cluster's date key is its newest member for descending and its oldest
  for ascending; its confidence key is its strongest member for descending and its weakest for
  ascending. Photos and clusters with no capture date sort last under both date directions rather
  than first or dropped, and a classification-id tiebreak keeps equal confidences or equal dates
  from reordering between identical requests. Clustering, pooling, and the pool cap are unaffected
  -- `sort` only reorders the response. `GET /library/clusters` takes the same `sort` query param
  and echoes it back on the response; a new "Sort" control on the Library page's Recommendations
  panel drives it, defaulting to "Surest first". The review queue's own triage ordering is
  untouched
- #164 fixed a production bug: opening the Library tab for a dog with hundreds of pending photos
  rendered every returned cluster's representative image plus up to 11 member thumbnails as plain
  `<img>` tags with no lazy-loading, firing dozens of simultaneous `GET /crops/{id}` requests that
  exhausted the shared SQLAlchemy connection pool (default `QueuePool` size 5 + overflow 10) and
  took down crop loading app-wide (review workspace, other dogs) for up to the 30s pool timeout.
  `ClusterCard.tsx`'s thumbnails now set `loading="lazy"`/`decoding="async"` so only on-screen
  images fetch eagerly, and `create_database()`'s engine pool is sized for a thumbnail burst
  (`pool_size=20`, `max_overflow=20`) with a short `pool_timeout=5` so genuine overflow fails fast
  instead of stalling every other crop request
- [#167](https://github.com/bradreimer/immich-dog-tagger/issues/167) removed the Timeline card
  from the per-dog Insights page: it duplicated the summary/Places data (first/last seen, location
  breakdown) as a flat, unsorted list of dates and place names with no actionable link. Frontend
  only -- `DogInsightsPage.tsx` no longer calls `getInsightsTimeline`, and the now-unused
  `getInsightsTimeline`/`TimelineEntry` were removed from `lib/api.ts`/`types/insights.ts`. The
  read-only `GET /api/dogs/{id}/insights/timeline` endpoint and `InsightsService` method are
  unchanged, pending a separate decision on whether to remove them too
- #166 a third path on each cluster card alongside Approve/"Not `<pet>`": a "Not `<identity>`?
  Assign to" picker lets the owner settle the selection on a specific different pet in one action
  when the cluster is correctly grouped but the proposed identity is wrong, instead of rejecting it
  back into the pending queue and hoping the right pet gets recommended for it later. Discovered
  along the way: `#142`'s "not-recommended" pool guard on `ClusterApprovalService.approve()` -- by
  design, refuses any identity the classifier never proposed for a crop -- would have silently
  skipped every member of a genuine reassignment, since the whole point is picking a pet that was
  never a candidate. Rather than reuse `approve()`, a new `reassign()` method and
  `POST /library/clusters/reassign` route apply the identical write (one ordinary correction per
  member, same batching/skip accounting) with only that one guard lifted; every other check
  (existing pet, no double-write over an existing review, matching species, duplicate/unbounded
  ids) is unchanged. The picker only lists active pets of the cluster's species, excluding the pet
  already selected on the panel
- [#171](https://github.com/bradreimer/immich-dog-tagger/issues/171) added a "Top photos"
  thumbnail grid to the per-dog Insights page: the identity's 10 highest-confidence confirmed
  photos, ordered by `PetOccurrence.confidence` descending (tiebreak occurrence id ascending). New
  `InsightsService.top_photos()` follows the existing "ranked collection" pattern
  (`timeline`/`places`/`people`) rather than the single-fact `InsightProvider` mechanism, per
  v1.6's own note that ranked collections don't fit that shape. New read-only
  `GET /api/dogs/{id}/insights/top-photos` endpoint (`limit` query param, default/max 10);
  `docs/specs/v1.6-pet-insights.md` amended with the new requirement/acceptance criterion.
- [#174](https://github.com/bradreimer/immich-dog-tagger/issues/174) fixed a production bug: a
  Reclassify job queued by #149's auto-reclassify-after-review (and a job created by
  `POST /schedules/{id}/run-now`, e.g. manually re-running a Full Pipeline schedule) stayed
  `PENDING` forever. `PipelineJobService.create_job()` only inserts the row -- only two things ever
  start a pending job: the cron scheduler (only for jobs tied to a `PipelineSchedule`, which
  neither of these has) and `PipelineJobDispatcher.trigger()` (previously called only from the
  manual `POST /jobs` "start" flow used by the Jobs page). `AutoReclassifyService.request()` and
  `run_schedule_now()` now call `dispatcher.trigger()` after creating the job, same as the Jobs
  page path; the scheduler's own cron-driven dispatch is untouched (still runs synchronously via
  the runner, never through the dispatcher)
- [#179](https://github.com/bradreimer/immich-dog-tagger/issues/179) added Photo Lookup: paste an
  Immich photo link into a new `/photo-lookup` page and see that exact photo with a colored box
  over each detected dog/cat, labeled with its predicted identity and confidence, with the option
  to correct a wrong one in place -- the reverse of #128's "View in Immich" link. New read-only
  `GET /photo-lookup/{immich_asset_id}` (detections/crops/classifications for an `Asset` looked up
  by Immich asset id) and `GET /photo-lookup/{immich_asset_id}/image` (fetches the original photo
  live from Immich via the existing server-side API key, since the pipeline deletes its local
  cached original once detection completes, per
  [docs/specs/storage-lifecycle-cleanup.md](specs/storage-lifecycle-cleanup.md); see
  [#206](https://github.com/bradreimer/immich-dog-tagger/issues/206) and
  [#213](https://github.com/bradreimer/immich-dog-tagger/issues/213) for why it's decoded/re-encoded
  server-side rather than proxied as-is); correction reuses
  the existing `POST /classifications/{id}/correct` endpoint rather than a new write path. See
  [docs/specs/photo-lookup.md](specs/photo-lookup.md).
- [#181](https://github.com/bradreimer/immich-dog-tagger/issues/181) v1.9.0 automatic
  spatial-proximity classification: the same idea v1.5.0's temporal weighting introduced, applied
  to location instead of capture date. `EmbeddingExample` gained a denormalized
  `latitude`/`longitude` snapshot (mirroring `captured_at`); `SimilarityScorer` now also computes a
  `spatial_weight` (Gaussian decay over haversine distance, ~2km scale, fail-open when a coordinate
  is missing on either side, floor so a lone identity's far-away examples still win with nothing
  closer-in-distance to compete against); `IdentityClassifier` ranks/selects candidates by
  `similarity * temporal_weight * spatial_weight` while still reporting each winning match's true,
  unweighted cosine similarity as confidence. A new `location-mismatch` review/library reason is
  checked alongside the existing `temporal-mismatch` (temporal takes precedence when both fire).
  See [docs/specs/v1.9-automatic-spatial-classification.md](specs/v1.9-automatic-spatial-classification.md)
  and [ADR-007](adr/ADR-007-automatic-spatial-proximity-classification.md).
- [#183](https://github.com/bradreimer/immich-dog-tagger/issues/183) v1.10.0 Pet Album Browsing:
  closes the "flat library grid" loose thread v1.8.0 left behind by bringing its
  similarity-clustering-with-confidence and multi-select-and-move treatment to a pet's
  already-*confirmed* photos, not only its pending recommendations. `ConfirmedClusterService`
  subclasses `RecommendationClusterService`, overriding only the pool query (confirmed --
  identity matches and a `ReviewAction` exists -- rather than unreviewed), so every clustering/
  sorting/excluded-candidate behavior is inherited unchanged. `ClusterApprovalService.move()` is
  the write: the confirmed-photo counterpart of `reassign()`, refusing a classification unless it
  is already confirmed as the claimed source pet (the opposite guard from `approve()`/
  `reassign()`'s "already-reviewed" refusal) -- the bulk form of the Library's existing per-photo
  "Correct to..." control, same `ClassificationCorrectionService.correct()` provenance. New
  `GET /library/clusters/confirmed` and `POST /library/clusters/move`, reusing the existing
  `ClusterProposalResponse`/`ClusterApprovalResponse` schemas. `ClusterCard` gained optional
  `onApprove`/`onReject` (omitted entirely for the confirmed view, which has no approve/reject
  concept) and configurable reassignment copy (`reassignPrompt`/`reassignVerb`/
  `reassignBusyLabel`/`representativeAlt`), so the new `ConfirmedClusterPanel` reuses it rather
  than duplicating the cluster-card UI. See
  [docs/specs/v1.10-pet-album-browsing.md](specs/v1.10-pet-album-browsing.md).
- [#185](https://github.com/bradreimer/immich-dog-tagger/issues/185) Photo Lookup gained an option
  to mark a detected box as "not a dog or cat" -- a YOLO false positive, distinct from a species or
  identity mistake. `Crop` gained a `not_animal` flag (mirrors how `species` already lives there);
  `FalsePositiveService.mark()`/`unmark()` toggle it, with new `POST`/`DELETE
  /crops/{crop_id}/not-animal` endpoints. #186 (same-day follow-up, reported by an owner using the
  feature) fixed the first cut's real bug: marking only set the flag and left the classification
  untouched, so a marked photo still showed "Confirmed as &lt;Dog&gt;" in Library and stayed in that
  dog's Immich album through sync. Marking now also settles the classification to Unknown through
  `ClassificationCorrectionService.correct(classification_id, None)` -- the same write path Review/
  Library corrections already use -- which drops it from the review queue, the dog's Immich album
  (next sync), the owner's Insights, and the reference set if it was ever learned as an example. See
  [docs/specs/photo-lookup.md](specs/photo-lookup.md)'s addendum.
- [#191](https://github.com/bradreimer/immich-dog-tagger/issues/191) fixed HEIC crops still coming
  out rotated relative to Immich after [#137](https://github.com/bradreimer/immich-dog-tagger/issues/137)'s
  EXIF-orientation fix -- a distinct defect in the same function, specific to HEIC (the default
  iPhone capture format). pi-heif's Pillow plugin resets the Orientation tag to `1` in its own
  decoded `info["exif"]` as soon as it opens a HEIC file, without rotating the pixel data to match;
  the real value survives only under the non-standard `image.info["original_orientation"]` key.
  `open_upright()` read orientation via `image.getexif()` -- what `ImageOps.exif_transpose()` reads
  -- which for HEIC always reported `1`, so orientation correction silently no-opped on every
  HEIC photo not shot in landscape, even on assets processed by the fixed pipeline. `open_upright()`
  now copies `info["original_orientation"]` into the Exif tag before transposing, when present; a
  no-op for every other format, since only pi-heif populates that key. Verified against real decoded
  HEIC fixtures (`tests/fixtures/heic_*.heic`, one per orientation value) rather than a synthetic
  in-memory image -- the bug only manifests once pi-heif has actually decoded a HEIC container.
- [#196](https://github.com/bradreimer/immich-dog-tagger/issues/196) v1.11.0 Library as a
  browse-and-correct catalogue: reverts the Library page's primary UI from v1.8.0's identity-first
  species/pet-selector-and-cluster-approval workspace back to a flat, independently filterable
  (species/pet/reviewed-status/capture-date-range, each a `<select>` or date input), sortable
  (capture date or confidence, applied in SQL before `LIMIT`/`OFFSET` so ordering holds across
  pagination, not just within one page), paginated (50/page) thumbnail grid with a per-photo
  details panel (name, species, confidence, capture date, location, review status, View in Immich,
  View in Photo Lookup, and an Edit link) -- see
  [ADR-008](adr/ADR-008-library-flat-browse-workspace.md) for why. The cluster-approval backend
  (`RecommendationClusterService`, `ConfirmedClusterService`, `ClusterApprovalService`,
  `/library/clusters*`) is deliberately not removed, only no longer reachable from the Library
  page's UI. The Review page now also accepts an optional `?classification_id=` query param
  (backed by a new `GET /classifications/{id}`) to edit any one classification directly -- the
  Library details panel's Edit link -- rendered with the same `ReviewCard` correction surface but
  no queue chrome (no Skip, no Previous/Next-through-queue, no filter buttons, no progress bar);
  `/review` with no param is unchanged. `ReviewCard` also gained a "Not a dog or cat" toggle
  (reusing the existing `POST`/`DELETE /crops/{crop_id}/not-animal` endpoints from issue #185),
  available in both the queue and the new single-item mode. `ReviewItem`/`ReviewItemResponse`
  gained `location` (derived from the cached `Asset.city`/`state`/`country` fields issue #94/#129
  already populate) and `not_animal`. See
  [docs/specs/v1.11-library-browse-and-correct.md](specs/v1.11-library-browse-and-correct.md).
- [#198](https://github.com/bradreimer/immich-dog-tagger/issues/198) reconnected FR-11's
  `UndetectedPanel` ("Photos with no detected pet") to `LibraryPage.tsx`. An earlier commit
  (`b39415c`) had removed its import and render call, reasoning the manual-tagging workflow
  "isn't needed," but never updated the spec or this file to match -- both still (correctly)
  describe FR-11 as shipped, and the backend (`/api/undetected`, `ManualTagService`, sync
  integration) and the component's own tests were left in place. The panel was reachable only
  from its own test file with nothing rendering it in the app; that was an unreviewed regression,
  not a followed-through product decision, so it is restored rather than removed. Landing after
  #196's flat-catalogue rewrite (which explicitly called this panel "unrelated and untouched"),
  `LibraryPage` now shows it whenever the pet filter is empty rather than only when a
  workspace-style `selectedPet` was unset, and a new `LibraryPage.test.tsx` case asserts it renders
  there and disappears once a pet filter is chosen, so a future refactor that drops it again fails a
  test instead of shipping silently.
- [#200](https://github.com/bradreimer/immich-dog-tagger/issues/200) descoped FR-11 for good: the
  manual-rescue workflow for photos the detector missed is removed, not just unreachable from the
  UI as `b39415c` left it before #198 restored it. Removed end-to-end: `UndetectedPanel` and its
  test, the render call in `LibraryPage.tsx` (and `LibraryPage.test.tsx`'s coverage of it, now
  asserting the section never renders), the frontend API client functions (`getUndetectedAssets`/
  `tagUndetectedAsset`/`untagUndetectedAsset`) and `types/undetected.ts`, the `/undetected` router
  (`api/routes/manual_tags.py`), `ManualTagService` (`services/manual_tags.py`), the
  `get_manual_tag_service` dependency, and the `UndetectedAsset*`/`ManualAssetTag*` response
  schemas. `ManualAssetTag` the SQLAlchemy model and `sync.py`'s use of it are deliberately left in
  place -- no new rows can be created once the API above is gone, but a photo tagged before this
  change keeps reaching its pet's Immich album rather than losing a correction that already
  happened; dropping that table would be a destructive schema change for existing installs this
  change doesn't need. Separately confirmed (and locked in with a new regression test,
  `test_detection_removes_cached_original_when_nothing_detected`) that `DetectionService.run()`
  already deletes a processed asset's cached original from `cache_dir` whenever a `crop_writer` is
  configured, regardless of whether any dog/cat was actually detected -- so a non-pet photo was
  already being dropped from the download cache; only the UI/API surface needed removing.
- [#206](https://github.com/bradreimer/immich-dog-tagger/issues/206) fixed the Photo Lookup image
  preview being a broken icon for any HEIC-original photo in Chromium/Firefox (Safari can decode
  HEIC natively, which masked the bug there). `GET /photo-lookup/{immich_asset_id}/image`
  previously proxied Immich's `/api/assets/{id}/original` bytes through as-is, with a media type
  derived from the asset's stored extension -- so a HEIC original was served with
  `Content-Type: image/heic`, which no standard browser can render inline. It switched to calling
  `ImmichClient.download_asset_preview()`, Immich's own full-resolution preview endpoint
  (`GET /api/assets/{id}/thumbnail?isThumb=false`), which Immich always transcodes to JPEG
  regardless of the original's format. **Superseded by #213** (below): that preview is generated by
  a transcoding pipeline independent of this app's own decoding, and isn't guaranteed to agree with
  it on orientation, which is what actually broke the overlay boxes.
- [#213](https://github.com/bradreimer/immich-dog-tagger/issues/213) fixed Photo Lookup's overlay
  boxes (the colored rectangles over each detected dog/cat, added by #179) silently disappearing or
  drifting out of alignment -- a regression from #206 above. `Detection.x1/y1/x2/y2` are computed
  against an `open_upright()`-decoded image (`src/immich_dog_tagger/images.py`, the same EXIF-
  orientation-corrected decode the detector/cropper/embedder all share); `PhotoLookupImage.tsx`
  positions each box as a percentage of the *displayed* image's natural dimensions, so the two only
  line up if the displayed image was decoded the same way. Immich's own preview/thumbnail pipeline
  (what #206 switched to) decodes and re-orients independently, and real-world Immich bugs exist
  where that disagrees with the source EXIF orientation (immich-app/immich#24807 and similar) --
  when it does, the boxes end up positioned against the wrong orientation/aspect ratio, off-frame
  more often than merely offset. `GET /photo-lookup/{immich_asset_id}/image` now downloads Immich's
  original bytes again (`ImmichClient.download_asset`, restoring the spec's original design) and
  decodes/re-encodes them itself through `open_upright()` + a new `images.to_jpeg_bytes()`, so the
  displayed image is guaranteed to be decoded identically to the one the boxes were computed
  against -- and still always comes back as browser-renderable JPEG regardless of the original's
  format, so #206's HEIC fix isn't lost. `ImmichClient.download_asset_preview()` (added by #206) is
  removed as unused.
- [#210](https://github.com/bradreimer/immich-dog-tagger/issues/210) fixed the Metrics page's
  Progress Over Time chart only ever showing the most recent 10 reclassification passes --
  `MetricsService`'s `history_limit` (`src/immich_dog_tagger/services/metrics.py`) hardcoded that
  cap, so once more than 10 `ClassificationPass` rows existed the chart's window slid forward and
  early history dropped out of the API response entirely (the rows themselves were never pruned
  from `state.db`, only left unqueried). `history_limit` now defaults to 500 -- effectively full
  history for any realistic Reclassify cadence, while still bounding the query. The chart would
  become illegible plotting hundreds of points, so a new `downsampleForDisplay` util
  (`ui/src/features/metrics/utils/downsample.ts`) samples the series down to at most 20 points for
  rendering, always keeping the first and last recorded pass so the line still spans the full
  history; axis scaling and the "Review Queue Reduction ... since pass #N" stat continue to read
  the full, undownsampled series so nothing sampled out shrinks the axis or changes what "first
  pass" means.
- [#194](https://github.com/bradreimer/immich-dog-tagger/issues/194) asset state reconciliation and
  pipeline self-healing, per
  [docs/specs/asset-state-reconciliation.md](specs/asset-state-reconciliation.md) (FR-1 through
  FR-12). `Scanner.scan()` now diffs a full (unlimited) scan's result set against `state.db` and
  moves any asset Immich no longer returns to a new terminal `AssetStatus.REMOVED`, cleaning up its
  cached original and any crop files not still backing an active-learning embedding example (FR-5);
  `ReviewQueryService.active_review()`/`review_queue_count()`, `GET /crops/{id}`, and
  `SyncService.sync()` all now exclude/skip a removed asset. A resurrected asset (reappears in a
  later scan) resets to `PENDING` rather than staying stranded. Separately, `DetectionService.run()`
  and `ClassificationService.classify()` gained per-asset/per-crop failure isolation mirroring
  `Downloader._download_one()`: a missing cached original or crop file routes the asset back to
  `DOWNLOAD_FAILED` (self-repairing on the next `download`/`detect` pass) instead of aborting the
  whole batch, and a genuine detection/classification error is recorded on that asset
  (`DETECTION_FAILED`/`CLASSIFICATION_FAILED`, now actually assigned for the first time) rather than
  failing the entire job -- resolving the "Detection/classification status ownership needs review"
  Known Issue below. `check-derived-data --repair` turns the existing report-only health check into
  an actual fix for missing downloads/crops (missing embedding sources still need a human, per the
  spec's scope).
- [#218](https://github.com/bradreimer/immich-dog-tagger/issues/218) tightened the review panel's
  desktop two-column layout, per
  [docs/specs/review-panel-space-efficiency.md](specs/review-panel-space-efficiency.md): the image
  and action columns now stretch to the same row height (`ReviewCard.tsx` grid, `ReviewImage.tsx`)
  instead of top-aligning, so a wide/landscape crop no longer leaves a large empty gap below it next
  to the taller action column; "Wrong species?" and "Not a dog or cat?" (`SpeciesChooser.tsx`,
  `NotAnimalToggle.tsx`) now share one compact card instead of a full card each. Confirmed "View in
  Immich"/"Edit Details" links (`ImmichPhotoLink`, `PhotoLookupLink`) were already present on every
  review item, queue and single-item edit view alike -- no gap there.
- [#221](https://github.com/bradreimer/immich-dog-tagger/issues/221) Photo Lookup can now correct a
  detection's species, not just its identity -- each row's identity `<select>` previously had no
  way to fix a crop assigned the wrong species in the first place (e.g. a cat cropped and
  classified as a dog), since it only ever listed identities of the species already on the crop.
  Reuses Review's existing species-correction write path as-is (`POST
  /classifications/{id}/species`, `ClassificationCorrectionService.correct_species`, #116) rather
  than adding a second one; the shared blue/amber palette moved to
  `ui/src/features/review/utils/speciesStyles.ts` so Review's `SpeciesChooser` and Photo Lookup's
  new compact per-row control read from the same place instead of each defining it. Correcting
  species re-fetches the full lookup afterward (identity/confidence can be reclassified server-side
  under the new species), the same pattern the existing not-animal toggle already uses.
- [#220](https://github.com/bradreimer/immich-dog-tagger/issues/220) stopped Photo Lookup from
  rendering an obviously-wrong overlay box for a `Detection` row that predates the EXIF-orientation
  fixes (#137/#192). That class of stale data was already known and documented (`docs/workflow.md`
  §7: crops/detections written before those fixes stay wrong until an operator manually runs
  `pipeline --force`), but #213/PR #214 made it newly visible -- once Photo Lookup's `/image` route
  started always rendering a correctly-upright image, a stale detection's pre-fix coordinates no
  longer had a similarly-wrong image to (coincidentally) line up with, so the box landed clearly off
  the animal instead. `PhotoLookupImage.tsx` now checks each detection's box against the loaded
  image's actual `naturalWidth`/`naturalHeight` (the same bounds check `crops.py:47` already applies
  at crop-write time, issue #88) and, when it falls outside the frame, shows a "Box not shown ...
  predates an orientation fix and needs reprocessing" banner instead of drawing a mispositioned box.
  Backend/`Detection` rows are untouched -- this is a display-only safeguard, not a fix for the
  underlying stale coordinates, which still needs the `pipeline --force` migration `docs/workflow.md`
  §7 describes (or a lighter-weight per-asset reprocessing path, which #220 leaves open).

## Current Milestone
v1.11.0 Library as a browse-and-correct catalogue ([#196](https://github.com/bradreimer/immich-dog-tagger/issues/196),
[docs/specs/v1.11-library-browse-and-correct.md](specs/v1.11-library-browse-and-correct.md)) is
**complete**. It reverts the Library page's primary UI to a flat, filterable, sortable, paginated
catalogue with a per-photo details panel, and lets the Review page edit any single classification
by id (the details panel's Edit link) -- see [ADR-008](adr/ADR-008-library-flat-browse-workspace.md)
for the full reasoning, including why the cluster-approval backend below is kept rather than
deleted.

Previously: v1.8.0 Library as an approval workspace ([#139](https://github.com/bradreimer/immich-dog-tagger/issues/139),
[docs/specs/v1.8-library-approval-workspace.md](specs/v1.8-library-approval-workspace.md)) is
**complete and released**. Scoped from
[docs/competitive-analysis-library-workflow.md](competitive-analysis-library-workflow.md), which
compared our library workflow against the faces workflows in Lightroom Classic, Immich, and Apple
Photos and found our labeling cost scaled with the number of photos while every competitor's scaled
with the number of subjects.

Every requirement shipped: FR-1 (#140, species -> pet selection as the Library's primary axis),
FR-2/FR-3 (#141, clustering and one-action cluster approval), FR-4 (#142, per-photo selection
within a cluster), FR-5 (#143, sorting by capture date or confidence), FR-6 (#144, "not this pet"
rejection), FR-8 (#146, detection coverage), FR-9 (#149, owner-facing tagging sensitivity and
auto-reclassify), and FR-10 (#148, merging two identities). FR-7 (#145, cold-start clustering) was
dropped as not planned -- the Review tab already serves the zero-example case. FR-11 (#147, tagging
a photo the detector missed) shipped, then was descoped and removed entirely by #200: see that
entry above.

Design decisions settled in review and recorded in the spec's "Resolved decisions": cold start stays
with the Review tab; approvals settle state and never trigger an Immich sync, generalized into
[ADR-006](adr/ADR-006-immich-operations-explicit-local-operations-on-demand.md); clustering is
agglomerative over cosine distance computed on demand, as a request-scoped read, with cluster
approval a synchronous write rather than a job (#141 measured a full 500-crop pool at ~0.3s, which
is what kept it a read); and a rejection lives in its own table rather than as a new `ReviewActions`
value.

No open questions remain. The one that outlived the release -- whether FR-8's coverage figure
should keep the headline share #146 shipped, or drop to the two plain counts review had settled on
-- was resolved in favour of leaving it as shipped: #146's denominator ("photos detection has
finished with") is better than the one that discussion assumed, it is stated on screen, and the raw
counts are still there. Recorded in the spec's "Resolved decisions".

Previously: no queued numbered milestone. v1.7.0 Pluginable Insight Providers (#110) shipped and is recorded
as completed in [docs/roadmap.md](roadmap.md); #111 (cancel a running job), #116/#117 (review
page species correction, predicted-identity highlight), and #125 (version display) followed as
additional reliability/UX fixes, along with #128 (link from a review item to its original photo
in Immich). `pyproject.toml`/`uv.lock`/the API app version had lagged at 1.6.0 through all of
that; this catches them up to 1.7.0 and tags the release. #155 followed, extending #125's
version display with the short commit SHA of the build (`GIT_COMMIT` build arg baked into the
Docker image by `docker-publish.yml` on every push to `main`), so the sidebar/settings version
now changes on every merge instead of only on explicit version bumps.

## Next Work
No queued numbered milestone -- v1.11.0 (#196) shipped complete, with one open question left in
its spec: what becomes of the cluster-approval workspace UI removed from the Library page (a
separate page, a second tab, or left unreachable until there's a concrete need). v1.10.0 (#183)
also shipped complete, including its own open question (FR-6-style "reject to no pet" from the
confirmed view was considered and left out of scope; see that spec's Open questions).

Loose threads, none of them blocking: #146's coverage figure is a share while
review settled on two plain counts (spec Open questions); and whether confirmed pets should
also be written to Immich's People surface rather than only albums remains an open ADR-sized
question, deliberately out of v1.8.0's scope.

New: [docs/specs/automation-schedule-settings.md](specs/automation-schedule-settings.md) scopes
moving Automation Schedules off Overview and into Settings, replacing the free-form
name+operation+cron builder with a fixed per-operation enable toggle + cron field in collapsible
sections (mirroring Immich's own Settings job-schedule pattern). Tracked as
[#188](https://github.com/bradreimer/immich-dog-tagger/issues/188).

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
- Endpoint-level API auth is not implemented yet.
- DT-1008's scale validation used synthetic-scale regression tests rather than a literal 30,000-real-image run (no GPU/Immich instance in the development environment); a real-library run is recommended before relying on it at that scale in production.
