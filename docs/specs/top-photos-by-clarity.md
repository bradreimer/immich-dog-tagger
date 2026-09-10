# Top Photos: Rank by Clarity, Include Every Source

Tracking issue: [#285](https://github.com/bradreimer/immich-dog-tagger/issues/285).

## Purpose

[#269](https://github.com/bradreimer/immich-dog-tagger/issues/269)
([docs/specs/insights-refinement.md](insights-refinement.md)) made `InsightsService.top_photos()`
filter to `ClassificationSources.AUTO` before ranking by `CropClassification.confidence`, because a
human-reviewed/manually-tagged occurrence always records `confidence = 1.0` by construction
(`ClassificationCorrectionService.correct()`), so ranking by raw confidence was really just
surfacing "photos a human tagged" instead of anything about the photo itself. That fix reframed the
section around classifier quality, at the cost of excluding every manually-tagged photo — often a
majority of an identity's confirmed photos in a well-reviewed library — from a section titled "Top
photos."

This spec changes the section's purpose again: instead of "photos the classifier was proud of," Top
Photos becomes "the clearest photos of this pet" — a collection meant to be nice to look at,
independent of which pipeline stage or human action produced the identification. That goal only
makes sense if every confirmed photo is eligible regardless of source, so the `AUTO`-only filter is
removed. Ranking needs a different signal in its place, since identity-classification confidence
(whether `AUTO`'s or the always-1.0 `REVIEW`/`MANUAL` value) says nothing about image quality.

## User story

As an owner viewing a dog or cat's Insights page, I want the Top Photos section to show the
clearest, best-looking photos of that pet — not just the ones a person happened to confirm most
recently or the ones the classifier scored highest — so the section is worth looking at regardless
of how each photo's identity was settled.

## Goals

- Include confirmed photos from every `ClassificationSources` value (`AUTO`, `REVIEW`, `MANUAL`) in
  Top Photos' candidate pool.
- Rank by a signal that reflects how clear/well-formed the photo of the animal is, not by
  identity-match confidence.
- Keep the computation deterministic, explainable, and read-time only (ADR-004): no new stored
  conclusion, no ML model invoked at request time, re-derivable from existing rows.
- Keep it bounded to one identity's own occurrences, matching every other `InsightsService` method
  (not a library-wide scan).

## Non-goals

- No new dependency, and no per-request image decoding/pixel analysis (e.g. blur/sharpness
  detection over the actual crop file). That would add real request-time cost and a new failure
  mode (missing/corrupt file) for a "nice to look at" section, and the pipeline already has a
  cheaper, already-computed signal that serves the same purpose (see Requirements).
- No change to what `ClassificationCorrectionService.correct()` or auto-classification write.
  Identity confidence keeps meaning exactly what it means today; this only changes what
  `top_photos()` ranks by.
- No change to `timeline`/`places`/`people`/`summary`/`cards` — unaffected.
- No UI change beyond this one section (thumbnail grid, its caption, and its empty-state copy).

## Requirements

### Rank by detection confidence, not identity confidence

Every `PetOccurrence` traces to exactly one `CropClassification` → one `Crop` → one `Detection` (the
YOLO bounding box that produced the crop in the first place). `Detection.confidence` is YOLO's own
confidence that the box contains an animal at all — a signal that is orthogonal to identity
matching and untouched by review/correction: a clean, well-lit, fully-visible, in-focus dog
produces a high-confidence detection, while a blurry, distant, small, or partially-occluded one
produces a lower-confidence detection, regardless of whose classification later confirmed *who* it
is. This is exactly the "how clear is this photo of the animal" signal the section needs, and it's
already computed and stored by the existing detection pass — no new computation, no file I/O, no
new dependency.

`InsightsService.top_photos()`:
- Drops the `occurrence.source != ClassificationSources.AUTO` filter — every source is now
  eligible.
- Orders by `occurrence.classification.crop.detection.confidence` descending, tiebreak by
  occurrence id ascending (matching the existing stable-order convention used by
  `timeline`/`place_counts`/`person_counts`).
- Keeps the existing defensive skip (issue #279) for an occurrence whose `classification` fails to
  resolve (dangling `crop_classification_id`), logged the same way as today.
- `TopPhoto` (and `TopPhotoResponse`) replaces its `confidence` field with `clarity`, carrying that
  same `Detection.confidence` value, so the API doesn't advertise a number that reads as identity
  certainty when it means something else now.

### UI

- `DogInsightsPage.tsx`'s Top Photos grid no longer shows a "NN.N% confidence" caption under each
  thumbnail (that number no longer being identity confidence made it liable to misread, and a raw
  detection score isn't itself meaningful to an owner). Each thumbnail instead shows the photo's
  captured date, reusing the page's existing `formatDate` helper — informative without requiring
  the reader to interpret an ML score.
- Empty-state copy for this section reverts from #269's "No auto-classified photos yet — every
  confirmed photo here was manually tagged" back to reusing the page's generic "no data yet" style,
  since the condition it described (all occurrences manually tagged) is no longer a reason for the
  section to be empty. It should only ever be empty when the identity has zero confirmed
  occurrences at all, which the surrounding `summary.total_photos === 0` branch already handles; the
  section's own empty state becomes a rarely-hit fallback (e.g. every occurrence dangling per issue
  #279) rather than an expected state, so its copy is simplified accordingly.

## Acceptance criteria

- Given an identity with a mix of `AUTO`, `REVIEW`, and `MANUAL` confirmed photos, `top_photos()`'s
  candidate pool includes all of them.
- Given photos with `Detection.confidence` 0.95, 0.80, and 0.60 across any mix of sources,
  `top_photos()` orders them 0.95, 0.80, 0.60 regardless of source or identity-classification
  confidence.
- Given an identity whose confirmed photos are *entirely* `REVIEW`/`MANUAL`, `top_photos()` no
  longer returns an empty list — it ranks them by their own detection confidence like any other
  occurrence.
- `GET /dogs/{id}/insights/top-photos` returns `clarity` instead of `confidence` in each entry.
- The Top Photos grid renders each photo's captured date instead of a confidence percentage.
- An occurrence with a dangling `crop_classification_id` (issue #279) is still skipped rather than
  crashing the endpoint.

## Open questions

- None.
