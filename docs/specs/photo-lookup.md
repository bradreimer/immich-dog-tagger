# Photo Lookup

## Purpose
Let an owner start from a photo *in Immich* -- a link shared in a chat, or opened while browsing
Immich directly -- and jump straight to what immich-dog-tagger thinks is in it, with the option to
correct it on the spot. Today the only entry points are the app's own `/review` queue and
`/library` page; there's no way to go the other direction (Immich photo -> app view). See issue
#179.

## User story
As a self-hoster, I want to paste an Immich photo link into immich-dog-tagger and see that exact
photo with a colored box around each dog it detected, labeled with its predicted identity, so that
I can immediately fix a wrong identity without hunting for the photo in the review queue or
library.

## Goals
- A new page where pasting a full Immich photo URL (`{IMMICH_URL}/photos/{assetId}`) renders that
  photo with a bounding box over each detected dog/cat.
- Each box is labeled with its predicted identity and confidence.
- A wrongly-identified dog/cat can be corrected from this view, through the same write path
  already used by Review and Library (`POST /classifications/{id}/correct`) -- no second way to
  write an identity correction.
- Clear, distinct messaging for: asset not yet scanned/processed by this instance, no dogs/cats
  detected in the photo, and a photo lookup that otherwise fails.

## Non-goals
- Detecting or classifying a photo on demand if it hasn't already gone through the pipeline. This
  reads existing `state.db` data (per ADR-001); it doesn't trigger `detect`/`classify`.
- Validating that the pasted URL's host matches the configured Immich instance. The asset id is
  looked up in `state.db` regardless of which host the pasted URL names; a wrong instance's asset
  id simply won't be found (same 404 as "not scanned yet").
- A new identity-correction UI pattern. Reuses the Library page's compact per-item `<select>`
  correction control rather than introducing a third design.

## Addendum: "not a dog or cat" (issue #185)

A photo lookup box can also be wrong in a third way, beyond a wrong species or a wrong identity: it
isn't a dog or cat at all (a YOLO false positive -- a stuffed animal, a shadow, a person). The owner
can mark a box this way from the same view, no identity required, and undo the mark. This is
recorded on the crop (`Crop.not_animal`, alongside `species`) via `FalsePositiveService` and
`POST`/`DELETE /crops/{crop_id}/not-animal`, and rendered as a dimmed, dashed box distinct from the
identified/unknown treatment. Deliberately narrow, per that issue's Out of scope: this does not
extend to Review/Library, does not affect the review queue or Metrics counts, and does not feed
into the classifier or learner -- each is a larger decision left for a follow-up if this becomes
useful in a second place.

## Requirements
- Parse the Immich asset id out of a pasted URL client-side, reusing/extending the existing
  `ui/src/lib/immich.ts` helpers rather than a new ad hoc parser.
- New read-only backend endpoint that looks up an `Asset` by `immich_asset_id` and returns its
  detections (`Detection.x1/y1/x2/y2`, `label`), each detection's crop species, and its
  classification (identity, confidence) when one exists -- 404 when no asset with that
  `immich_asset_id` has been scanned.
- New backend endpoint that serves the full original photo for display. The pipeline deletes its
  local cached original once detection completes (`docs/specs/storage-lifecycle-cleanup.md`), so
  this proxies the bytes live from Immich (`ImmichClient.download_asset`, the same server-side API
  key every other Immich call already uses) rather than reading a local file that usually no
  longer exists.
- Frontend renders the photo at natural size (no letterboxing) with an absolutely-positioned
  overlay box per detection, sized as a percentage of the image's natural dimensions so boxes stay
  aligned regardless of the rendered display size.
- Box color follows the existing status/categorical palette (`docs/specs/ux-principles.md`):
  distinct treatment for "identified" vs. "unknown identity" boxes.
- Correcting a box's identity calls the existing `POST /classifications/{id}/correct` endpoint and
  updates that box's label in place, matching the optimistic-update pattern Library already uses.

## Acceptance criteria
- Pasting a valid Immich photo URL for a scanned, detected photo shows that photo with one box per
  detected dog/cat, each labeled with its predicted identity (or "Unknown") and confidence.
- Pasting a URL for an asset not yet scanned/detected by this instance shows a clear "not found"
  message, not a blank page or raw error.
- A photo with zero detections shows the photo with a clear "no dogs or cats detected" message,
  distinct from "not found".
- Correcting an identity from a box updates that box's label without a full page reload and
  without needing to separately visit Review or Library.
- A URL that can't be parsed as an Immich photo link (malformed, wrong shape) is rejected client-
  side with a helpful message before any request is made.

## Open questions
- None.
