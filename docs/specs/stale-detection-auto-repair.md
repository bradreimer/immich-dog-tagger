# Stale-Detection Auto-Detection & Batch Repair

## Purpose
Let a user find out which photos have detections left stale by a past EXIF-orientation decode
bug, and repair that subset in one batch action from the Overview page, instead of having to
notice and fix each photo one at a time via the per-photo "Repair" action.

## User Story
As a user who has been using the per-photo Repair button on Review/Photo Lookup, I want to know
how many photos in my library still have stale detections and fix them together from Overview,
so I don't have to stumble across each one individually to know it needs repairing.

## Context
`AssetRepairService.repair()` (`services/asset_repair.py`, issue #226) force-reprocesses one
asset's download/detect/classify pipeline to fix detections whose stored box coordinates predate
the EXIF-orientation fix (issues #137/#213/#220 -- `images.py`'s `open_upright()`). It is
deliberately per-asset and human-triggered: `DetectionService.run(force=True)` deletes and
recreates `Detection` rows, which cascades to delete any `CropClassification`/`ReviewAction`
already recorded against them. Repairing an already-reviewed photo discards its review history --
an accepted cost of an explicit, one-photo action, not something to do silently at scale.

Today there is no way to find affected photos other than noticing a wrong-looking box while
reviewing. Two things block a straightforward "just re-run detection on everything and diff" auto-
detector:
- `Detection` has no timestamp or version column (`models.py:304-328`), so nothing records when a
  given detection was computed, and there's no way to tell an old (possibly affected) detection
  from a fresh one after the fact.
- `DetectionService.run()` deletes each asset's cached original from disk once it reaches
  `DETECTED` (`detection.py:260-273`), so the upright image a fresh detection would need is
  usually already gone locally -- re-running detection on the whole library to compare would
  require re-downloading most of it.

There is a cheaper, precise (not heuristic-guessing) signal available without re-downloading or
re-running detection, though: Immich's own asset metadata. The same `/api/search/metadata`
response the scanner already fetches for `exifInfo.latitude/longitude/...` (issue #94,
`immich.py:121-149`) also carries `exifInfo.exifImageWidth`/`exifImageHeight`/`orientation` for
every asset -- none of which this app captures today. For any photo whose EXIF orientation implies
a 90/270-degree rotation (values 6/8, and their mirrored counterparts 5/7), the upright
width/height are the *stored* height/width swapped. A `Detection` box computed before the fix was
decoded without applying that rotation, so its `x2`/`y2` extend into what are, post-rotation, the
wrong axes -- concretely, `x2` or `y2` exceeds the upright dimension on that axis but fits within
the un-rotated (raw sensor) dimensions. That mismatch is checkable arithmetic against metadata
already available from Immich, with no local file and no re-detection required.

This only catches the 90/270-rotation subset. A 180-degree flip or a mirrored orientation (values
2/3/4) doesn't change width/height, so an affected box from one of those stays in-bounds -- wrong
content, but not geometrically provable without the pixels. That subset stays undetectable short
of re-running detection on the actual image, which is what the existing per-photo Repair already
does on demand.

## Goals
- Capture Immich's `exifInfo.exifImageWidth`/`exifImageHeight`/`orientation` for each asset (like
  the existing `latitude`/`longitude`/etc. fields, from the same already-fetched response).
- Add a diagnostic check that flags assets whose stored `Detection` box(es) are geometrically
  inconsistent with the asset's upright dimensions per the rule in Context, and surface a count
  of affected photos (mirroring how `DerivedDataService`/`GET /diagnostics` already surfaces a
  missing-file count on Overview, per `asset-state-reconciliation.md` FR-12).
- Let the user trigger `AssetRepairService.repair()` across exactly that flagged set from
  Overview, in one action, with the same repair behavior (and the same review-history cost) as
  today's per-photo button -- this is a scoped batch of the existing action, not a new repair
  mechanism.
- Make the review-history cost visible before the user commits to the batch: how many of the
  flagged photos have recorded review history that repairing them will discard.

## Non-goals
- Detecting every possible stale/wrong detection (180-degree/mirrored cases) -- out of reach
  without re-running detection on each candidate; not attempted by this pass.
- A general "re-check my whole library for any drift" scanner -- scoped to this one known,
  geometrically-provable defect class.
- Any automatic/scheduled repair -- this stays a human-triggered action from Overview, not
  something a pipeline run does on its own.
- Retroactively distinguishing already-affected detections from fine ones via a stored
  version/timestamp column -- adding one now only helps prevent a *future* recurrence (the
  existing backlog has no such marker either way); not needed for this pass, which detects the
  current backlog geometrically instead.

## Requirements
- **FR-1**: Extend `ImmichAsset`/`_parse_immich_asset` (`immich.py`) to read
  `exifInfo.exifImageWidth`, `exifInfo.exifImageHeight`, and `exifInfo.orientation`, defensively
  (`.get()`, tolerating an older Immich server or a photo with no EXIF), matching the existing
  latitude/longitude fields' pattern.
- **FR-2**: Add nullable `Asset.exif_width` / `Asset.exif_height` / `Asset.exif_orientation`
  columns (migration), populated by `Scanner` the same way `latitude`/`longitude` already are.
  Existing assets get these backfilled the next time `scan` runs against them, not by a one-off
  data migration.
- **FR-3**: A diagnostic check (new method on `DerivedDataService`, or a sibling service if that
  grows unwieldy) computes, for each asset with `exif_orientation` in {5, 6, 7, 8} (a 90/270-degree
  rotation) and at least one `Detection`, whether any detection's `x2 > exif_height` or
  `y2 > exif_width` (upright bounds) while fitting within the raw `exif_width`/`exif_height` --
  i.e., geometrically consistent with a pre-rotation-fix decode. Assets with no captured
  orientation (not yet re-scanned under FR-2) are excluded, not guessed at.
- **FR-4**: `GET /diagnostics` includes this count, and the Overview page adds a health tile for
  it (same visual pattern as the existing Derived Data tile, `OverviewPage.tsx:314-353`).
- **FR-5**: The diagnostics response for this check also includes how many of the flagged assets
  have at least one recorded `ReviewAction` -- the count of review history a batch repair would
  discard -- so the UI can show it before the user confirms.
- **FR-6**: A new endpoint (e.g. `POST /diagnostics/stale-detections/repair`) runs
  `AssetRepairService.repair()` for every currently-flagged asset and returns a summary (repaired
  count, failed count), reusing the existing per-asset service rather than a new repair code path.
- **FR-7**: The Overview tile's batch-repair action requires an explicit confirmation step that
  states the review-history count from FR-5 before proceeding (per this repo's UX principle of
  confirming destructive/irreversible actions, `ux-principles.md`).

## Acceptance Criteria
- After a `scan` run, an asset whose Immich EXIF orientation requires a 90/270-degree rotation has
  `exif_width`/`exif_height`/`exif_orientation` populated in `state.db`.
- A library containing at least one photo with a geometrically-stale detection (box coordinates
  inconsistent with its upright dimensions) shows a non-zero count on a new Overview tile; a
  library with none shows zero, matching what `GET /diagnostics` reports.
- Triggering the batch action repairs every flagged asset (verified via
  `check-derived-data`-style before/after counts) and leaves not-flagged assets untouched.
- The confirmation step shown before running the batch states how many flagged assets have
  existing review history that will be discarded, matching the actual `ReviewAction` count for
  that set.
- A photo with a 180-degree or mirrored stale detection is correctly *not* flagged (documented
  Non-goal), rather than silently mis-flagged as fine.

## Open Questions
- Should assets with recorded review history be excluded from the one-click batch by default,
  requiring a separate, explicit "include reviewed photos too" opt-in -- or is stating the count
  up front (FR-5/FR-7) sufficient? This is the main product decision before implementation: the
  worse failure mode is a user batch-repairing away review history they didn't realize was there.
- For a large library, is a per-asset SQL check (FR-3) fast enough to run synchronously for
  `GET /diagnostics`, or does it need the same async job treatment `check-derived-data` uses for
  large libraries?
- Do we backfill `exif_width`/`exif_height`/`exif_orientation` for already-scanned assets via a
  dedicated one-off command, or accept that the count is incomplete until the user's next regular
  `scan` naturally re-visits each asset (FR-2 already leans toward the latter, but this should be
  an explicit decision, not a default)?
- Is `Detection.x2 > exif_height` (etc.) exactly right, or does Immich's `exifImageWidth`/
  `exifImageHeight` sometimes already reflect the rotated (display) dimensions rather than the raw
  sensor dimensions, depending on server version -- this needs confirming against a real Immich
  instance/API response before implementation, not assumed from the field names.
