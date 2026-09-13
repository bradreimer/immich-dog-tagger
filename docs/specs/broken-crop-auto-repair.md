# Broken Crop Auto-Detection & Batch Repair

## Purpose
Let a user find every Library photo whose crop thumbnail is broken (`GET /crops/{id}` 404s
because the file is missing on disk even though the `Crop` row still exists) and repair the
whole set in one action from Overview, instead of noticing each broken thumbnail while browsing
Library and repairing it one photo at a time.

## User Story
As a user who has finished reviewing and now finds broken crop thumbnails while browsing Library,
I want the app to find every photo with a missing crop file and repair them together, so I don't
have to open each one individually to discover it needs repairing.

## Context
`GET /crops/{id}` (`api/routes/crops.py`) serves `Crop.path` as a file response and 404s when
that path doesn't exist on disk -- which is exactly what the reported log shows for several crop
IDs. The DB row (`Crop`, `models.py:572-611`) doesn't track file existence, so nothing flags this
drift until a client actually requests the file.

Detecting this is not new work: `DerivedDataService.check()` (`services/derived_data.py`) already
walks every non-removed `Crop.path` and checks it against disk, populating
`DerivedDataReport.missing_crops`. That count is already surfaced today via `GET /diagnostics` and
an Overview "Derived Data" tile (`OverviewPage.tsx:316-323`).

Repairing it is not new work either: `DerivedDataService.repair()` already exists and does
precisely this -- for each affected asset it deletes the stale `Detection`/`Crop` rows and routes
the asset back to `AssetStatus.DOWNLOADED` (or `DOWNLOAD_FAILED` if the original download is also
missing) so the next `detect` pass regenerates the crop from scratch. The gap is that this method
is wired to the CLI only (`immich-dog-tagger check-derived-data --repair`, `cli.py:109-133`) --
there is no API route or UI button that calls it, unlike the sibling "Stale Detections" tile,
which already has a full check-count-then-batch-repair flow
(`docs/specs/stale-detection-auto-repair.md`, `services/stale_detection.py`,
`api/routes/diagnostics.py`, `StaleDetectionRepairAction.tsx`). So the "automated way" being asked
for mostly exists already; it just isn't reachable from the browser.

One existing behavior needs to be carried over faithfully and made visible to the user, not
quietly inherited: `repair()` doesn't regenerate only the one missing crop on a photo -- for an
affected asset it deletes *all* of that asset's `Detection` rows (`derived_data.py:190-201`),
which cascades to delete every `CropClassification`/`ReviewAction` tied to them
(`models.py` cascades on `Detection` -> `CropClassification` -> `ReviewAction`), then re-routes
the whole asset through `detect` again. If a photo has one broken crop alongside other,
undamaged, already-reviewed crops, repairing it discards that review history too. This is the
same tradeoff `AssetRepairService.repair()` and the Stale Detections batch action already make
deliberately (`docs/specs/stale-detection-auto-repair.md`'s Context/FR-5/FR-7) -- it should get
the same "state the cost, require confirmation" treatment here, not a silent batch run.

## Goals
- Expose `DerivedDataService.repair()`'s missing-crops path via an API endpoint, instead of
  CLI-only.
- Add a "Repair" action to Overview's existing Derived Data tile (currently count-only), matching
  the Stale Detections tile's visual and interaction pattern.
- Before running, show how many of the affected assets have recorded review history
  (`ReviewAction`) that repairing will discard, and require explicit confirmation before
  proceeding -- mirroring `stale-detection-auto-repair.md` FR-5/FR-7.
- Make per-asset failures during a batch non-fatal: one asset failing to repair shouldn't abort
  the rest of the batch or leave the DB session in a half-committed state.

## Non-goals
- No new detection logic for broken crops -- reuse `DerivedDataService.check()`'s existing
  `missing_crops` scan verbatim.
- Not a new repair mechanism -- reuse `DerivedDataService.repair()` verbatim. Making it more
  surgical (repairing only the missing crop instead of discarding all of an asset's detections) is
  a separate follow-up; out of scope here (see Open Questions).
- No automatic/scheduled repair -- stays a human-triggered batch action from Overview, consistent
  with the Stale Detections precedent and this repo's review-history handling policy.
- Doesn't add UI/API for `missing_downloads` or `missing_embedding_sources` beyond preserving
  today's count display -- scope is the crops case because that's the failure the user hit.

## Requirements
- **FR-1**: A new endpoint (e.g. `POST /diagnostics/derived-data/repair`) calls
  `DerivedDataService.repair()` and returns its summary (`downloads_repaired`, `crops_repaired`,
  `total_repaired`) as JSON.
- **FR-2**: `GET /diagnostics` includes, alongside the existing `missing_crops` count, how many of
  the affected assets have at least one recorded `ReviewAction` -- the review history a repair
  would discard -- analogous to `stale-detection-auto-repair.md` FR-5.
- **FR-3**: Overview's Derived Data tile gets a "Repair" action (disabled/hidden when
  `total_missing == 0`), matching the Stale Detections tile's pattern.
- **FR-4**: The Repair action requires an explicit confirmation step stating the
  review-history-at-risk count from FR-2 before calling FR-1's endpoint, per this repo's UX
  principle of confirming destructive/irreversible actions (`ux-principles.md`).
- **FR-5**: After repair, Overview's counts refresh to reflect the new state (repaired assets
  routed back to `DOWNLOADED`/`DOWNLOAD_FAILED`, pending the next `detect`/pipeline pass -- the
  repair endpoint itself doesn't re-detect synchronously, same as today's CLI behavior).
- **FR-6**: A failure repairing one affected asset is isolated (logged, skipped, session state left
  consistent) and doesn't abort the rest of the batch, matching
  `StaleDetectionService.repair()`'s per-asset isolation (`services/stale_detection.py:159-179`).
  `DerivedDataService.repair()` today has no such isolation -- a single failure partway through
  its loop would leave earlier in-session changes uncommitted; this needs fixing as part of this
  work, not just reusing the method as-is.

## Acceptance Criteria
- A library with at least one crop file missing from disk shows a non-zero repair-eligible count
  on the Overview Derived Data tile, matching what `GET /diagnostics` reports.
- Triggering the batch action repairs every currently-flagged asset (verified via
  `check-derived-data`-style before/after counts) and leaves unaffected assets untouched.
- The confirmation step shown before running the batch states how many affected assets have
  existing review history that will be discarded, matching the actual `ReviewAction` count for
  that set.
- One asset failing to repair (e.g. a permissions error deleting its stale crop file) doesn't
  prevent the rest of the batch from repairing successfully, and is reflected in the returned
  summary.
- After a batch repair, a subsequent normal `detect` pipeline pass regenerates crops for every
  repaired asset, and `GET /crops/{id}` for those photos no longer 404s.

## Open Questions
- Should `DerivedDataService.repair()` become more surgical -- regenerating only the crop(s)
  actually missing on a photo, rather than deleting every `Detection` (and its review history) on
  that asset? Today's all-or-nothing behavior is an existing, deliberate tradeoff elsewhere
  (`AssetRepairService.repair()`), but it's worth an explicit decision here rather than assuming
  1:1 reuse is the right level of blast radius for what's meant to be a routine, low-friction fix.
- Does a large `missing_crops` backlog need async job treatment rather than a synchronous
  request/response, the same concern `stale-detection-auto-repair.md` raised for its own check
  (issue #317's connection-pool pressure)?
- Should this same batch action also cover `missing_downloads` (already computed, already in
  `DerivedDataRepairSummary`, currently unreachable from the UI), or stay scoped to crops for this
  pass and treat downloads as a follow-up?
