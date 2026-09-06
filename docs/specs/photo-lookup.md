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

## Addendum: "not a dog or cat" (issue #185, corrected by #186)

A photo lookup box can also be wrong in a third way, beyond a wrong species or a wrong identity: it
isn't a dog or cat at all (a YOLO false positive -- a stuffed animal, a shadow, a person). The owner
can mark a box this way from the same view, no identity required, and undo the mark. This is
recorded on the crop (`Crop.not_animal`, alongside `species`) via `FalsePositiveService` and
`POST`/`DELETE /crops/{crop_id}/not-animal`, and rendered as a dimmed, dashed box distinct from the
identified/unknown treatment.

The same control also covers a second case, formalized in
[ADR-009](../adr/ADR-009-manual-reclassification-contract.md): a box that does show a dog or cat,
but one the owner doesn't recognize or doesn't want to label right now. Both cases settle to the
same Unknown state and share the one flag -- nothing distinguishes which reason a mark was made
for.

#186: the first cut (issue #185) only set the flag and left the crop's classification untouched,
so a marked photo kept showing "Confirmed as &lt;Dog&gt;" in Library and stayed in that dog's Immich
album through sync -- the exact case this feature exists to fix ("I have a wrong image in an
album"). Marking now also settles the classification to Unknown through the same write path Review/
Library corrections use (`ClassificationCorrectionService.correct(classification_id, None)`), which
is what makes the mark actually take effect everywhere an identity is read from: it drops out of
the active review queue, out of any Immich album on the next `sync`, out of the owner's Insights
(the `PetOccurrence` row is cleared), and out of the reference set if the crop was ever learned as
an example (so it stops teaching the classifier its own mistake). Unmarking only clears the flag --
it does not restore the pre-mark prediction, which is gone the moment it's settled, the same as any
other review correction today; the owner picks the right identity afterward through the existing
identity control if needed.

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

## Addendum: link from Review (issue #190)

Beyond pasting an Immich URL by hand, `/photo-lookup?assetId={immich_asset_id}` runs the lookup for
that asset automatically on load, skipping the paste step. This is the entry point the Review
card's "View in Photo Lookup" link uses (`item.immich_asset_id` is already known there, so no URL
needs to be constructed or parsed) -- it opens in a new tab so the reviewer doesn't lose their place
in the review queue. The manual paste-a-URL flow is unchanged.

## Addendum: correct species too (issue #221)

A photo lookup box's identity `<select>` only ever offers identities of the species the crop was
already assigned -- if that assignment itself is wrong (a cat cropped and classified as a dog),
there's no identity in the list that fixes it. Each row now also carries a compact Dog/Cat control
alongside the identity select, reusing Review's existing species-correction write path (`POST
/classifications/{id}/species`, `ClassificationCorrectionService.correct_species`, issue #116) and
its blue/amber palette (`ui/src/features/review/utils/speciesStyles.ts`, shared with Review's
`SpeciesChooser` rather than redefined). Correcting species can reclassify identity/confidence
under the new species server-side, so the page re-fetches the full lookup afterward rather than
patching the row in place, the same as the not-animal toggle does. The control is hidden for a
detection marked "not a dog or cat" or one with no classification yet, matching the identity
select's own "nothing to correct against" cases.

## Addendum: classify a pending detection (issue #245)

A detection can reach Photo Lookup with a `Crop` but no `CropClassification` at all -- the
classify pipeline stage simply hasn't reached it yet (e.g. the asset was re-detected by "Repair"
or scanned recently and the scheduled `classify` run hasn't caught up, or a prior classify chunk
failed and left the asset's other crops pending). Until #221, every correction control already
required a `classification_id` to write against, so a detection in this state rendered as a bare
species badge and "Not classified yet" with nothing to fix it except a full "Repair" -- which forces
re-download/re-detect and, per `AssetRepairService`, discards any review already recorded for the
photo's *other* detections. That's a disproportionate hammer for "this one box was never classified."

Each such row now also gets a "Classify" action that runs `ClassificationService.classify(mode=
PENDING, asset_id=...)` scoped to this photo -- the same non-destructive, idempotent step the
scheduled `classify` job already runs library-wide, just triggered on demand for one photo instead
of waited on. It only classifies crops that have no `CropClassification` yet; it never touches
already-classified or already-reviewed detections on the same photo. Once it produces a
classification (an automatic best-guess identity, or Unknown if none clears the confidence
threshold), the row immediately gets the same species-correction and identity-`<select>` controls
every other row has -- reusing `POST /classifications/{id}/species` and `POST
/classifications/{id}/correct`, no new correction path.

This is a deliberate, narrow exception to this spec's "doesn't trigger detect/classify" non-goal,
same as the "Repair" action already is: both are explicit, human-triggered, single-photo actions,
not something run automatically or library-wide from a read of Photo Lookup.

### Requirements
- New endpoint, `POST /photo-lookup/{immich_asset_id}/classify-pending`, calling
  `ClassificationService.classify(mode=ClassificationMode.PENDING, asset_id=...)` for the looked-up
  asset only.
- A row with `classification_id === null` shows a "Classify" action instead of the identity
  `<select>`/"Not classified yet" text. Clicking it calls the new endpoint, then re-fetches the full
  lookup (same pattern as the not-animal toggle and species correction), which fills in every
  now-classified row's species and identity controls.
- A no-op when the asset has no pending crops (e.g. a second click, or a race with the scheduled
  classify job) -- calling `classify(mode=PENDING)` is already idempotent since it only selects
  crops without a classification.
- The "Not a dog or cat" toggle remains available on a pending row too (`FalsePositiveService.mark()`
  already tolerates `crop.classification is None`) as the existing way to settle a genuine
  non-animal box without waiting on classification.

### Acceptance criteria
- A detection with no classification shows a "Classify" button, not a dead-end "Not classified yet"
  label.
- Clicking it turns that row (and any other pending row on the same photo) into a normal
  species-correctable, identity-correctable row, without discarding any other detection's existing
  classification or review status on that photo.
- Correcting a photo that has zero pending crops (e.g. everything already classified) never shows
  this action.

## Open questions
- None.
