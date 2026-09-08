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

## Addendum: highlight hovered detection's box (issue #251)

With several overlapping detections, it's hard to tell by eye which numbered row in the detection
list below the photo belongs to which box on it. Hovering a row now highlights that detection's box
on the photo: `PhotoLookupPage` lifts a `hoveredDetectionId` piece of state, `DetectionList` reports
hover in/out per row (keyed by `detection.detection_id`, the same id boxes are already keyed by),
and `PhotoLookupImage` renders the matching box with an added highlight ring and raises it above
sibling boxes (`z-index`) so it stays visible under overlap. The existing identified/unknown/
not-animal color coding and label are unchanged -- the highlight is an additional state layered on
top, not a replacement palette. Reverse direction (hovering a box highlights its row) is out of
scope for this pass.

## Addendum: manually map a crop-less or mislabeled detection to a dog/cat (issue #261)

A `Detection` only gets a `Crop` -- and therefore anything to classify -- when its raw `label` is
already `dog` or `cat` (`CropWriter._DETECTABLE_LABELS`, `crops.py`). A YOLO detection labeled
something else entirely (`person`, `sheep`, any other COCO class) never becomes a crop, even when
the box is genuinely a dog or cat the detector misclassified. Confirmed live against a production
instance (asset `2703e964-f77e-4765-a9b6-c981805c382c`): two detections labeled `person` and
`sheep`, neither with a `crop_id`, both permanent dead ends -- no control on the page can tell the
app "this box is actually a dog." Worse, the badge shown today actively misleads:
`DetectionList.speciesLabel()` renders any non-`cat` label as "Dog", so a `person` or `sheep`
detection shows a "Dog" badge, masking the real problem (there's no crop) behind a label that
looks like species is already settled.

This is a different, narrower case than the "classify a pending detection" work attempted in
#245/#249, shipped, found non-functional in production (#253), and fully reverted in #256: that
work was about a detection that already had a `Crop` but no `CropClassification` yet, fixable by
re-running the automatic classifier (`ClassificationService.classify(mode=PENDING)`). This
addendum is about a detection with no `Crop` at all -- the automatic classifier never runs on it
because nothing ever creates a crop for it to run against. #256's revert explicitly named this as
its own follow-up: "explicitly map a crop-less detection to a dog/cat as a manual override, rather
than depending on an automatic classifier run." Given that #245's automatic-rerun approach failed
silently in a way that was never root-caused, this addendum deliberately avoids the same shape of
fix: no dependency on `ClassificationService`/`IdentityClassifier` inference for this path at all.
A human names the species and identity directly, in one synchronous action, and the row either
visibly updates or a clear error is shown.

### Goals
- A crop-less detection row (`crop_id === null`) shows its actual YOLO `label` (e.g. "sheep",
  "person"), not a "Dog" badge implying species is already settled.
- From that row, a human can say "this is actually a dog/cat" and directly pick the identity (or
  leave it at species-only/Unknown) in one action -- no separate crop-generation step, no
  dependency on a classifier run succeeding.
- The same row can instead be dismissed as "not a dog or cat" (confirming the detector was right
  not to treat it as one), consistent with every other detection's tri-state (identified / Unknown
  / not-animal) contract from [ADR-009](../adr/ADR-009-manual-reclassification-contract.md).
- The new crop is indistinguishable afterward from an ordinary pipeline-generated one: it can be
  corrected again, learned as a reference example, synced to Immich, and counted in Insights/
  Metrics exactly like any other classified crop.

### Non-goals
- Reopening or re-attempting #245's automatic "classify a pending detection" flow. That case
  (`crop_id` set, `classification_id` null) is unchanged by this addendum and still shows "Not
  classified yet" with no action, per #256.
- Detecting new bounding boxes YOLO missed entirely. This only re-labels a box the detector already
  drew but assigned the wrong (non-dog/cat) class to -- it does not let a human draw a new box from
  scratch.
- Batch/bulk mapping across multiple photos. This is a single-detection, single-photo action from
  Photo Lookup, matching every other correction control on this page.

### Requirements
- New backend endpoint, e.g. `POST /photo-lookup/{immich_asset_id}/detections/{detection_id}/assign`,
  body `{species: "dog" | "cat", identity: string | null}`:
  - 404 if the asset or detection isn't found, or the detection already has a `Crop` (this path is
    only for the crop-less case; an existing crop is corrected through the existing species/
    identity controls instead).
  - Downloads the original photo live from Immich (`ImmichClient.download_asset`, the same call the
    existing `/photo-lookup/{id}/image` endpoint already makes -- the pipeline's local cached
    original is long gone by the time a human notices this in review, per
    `docs/specs/storage-lifecycle-cleanup.md`).
  - Crops the detection's stored `(x1, y1, x2, y2)` out of that image, reusing `CropWriter`'s
    padding/box-expansion/orientation logic (`crops.py`) rather than reimplementing it, and writes
    the result to the same crop directory pipeline-generated crops use.
  - Creates the `Crop` (species = the human's chosen species) and a `CropClassification` with
    `identity` = the human's choice (or `None` for species-only/Unknown), `confidence = 1.0`,
    `source = ClassificationSources.REVIEW` -- the same values `ClassificationCorrectionService.
    correct()` already uses for a human decision, so this crop is never mistaken for a lower-
    confidence auto-classification anywhere confidence is read.
  - Records a `ReviewAction` and feeds the `Learner` a new reference example exactly as `correct()`
    does today (a manually-assigned identity is exactly as much ground truth as a queue correction
    -- see CLAUDE.md's "human review is authoritative input").
  - Runs `PetOccurrenceService.sync_classification()` so Insights picks it up immediately, matching
    every other write path.
- A parallel "not a dog or cat" action for a crop-less row: creates the `Crop`/`CropClassification`
  the same way, but immediately flags `Crop.not_animal = True` and settles identity to Unknown
  through the same call `FalsePositiveService.mark()` already makes -- so this is truly the same
  tri-state as any other row, not a fourth state.
- `DetectionList.tsx`: a crop-less row gets a "Map to dog/cat" action (species picker + identity
  `<select>`, or defer to Unknown) alongside a "Not a dog or cat" button, replacing the current bare
  "Not classified yet" text. `speciesLabel()` shows the detection's real raw label for a crop-less
  row instead of coercing it to "Dog".
- `PhotoLookupPage` re-fetches the full lookup after a successful assign, the same refresh-not-patch
  pattern already used for species correction and the not-animal toggle (both of which can also
  change more than the one field being edited).

### Acceptance criteria
- Given a detection with no crop (any raw YOLO label), the Photo Lookup row shows that real label,
  not a "Dog" badge.
- A human can pick species + identity for that row in one action; the row becomes an ordinary
  classified row afterward (species toggle, identity `<select>`, 100% confidence) with no page
  reload.
- A human can instead mark that row "not a dog or cat"; the row renders exactly like an existing
  not-animal crop (dimmed/dashed box, "Not a dog or cat" text, "Undo" available).
- The newly created classification is excluded from the active review queue (it carries a
  `ReviewAction`), appears in Insights (`PetOccurrence` reflects it), feeds the learner (a new
  reference example exists for a named identity), and is picked up by the next `sync` (it joins the
  identity's Immich album).
- Attempting this action on a detection that already has a crop is rejected (400/404, not a silent
  no-op) -- that case goes through the existing species/identity controls.
- A test in `tests/api/test_photo_lookup.py` mirrors the real bug report this addendum is based on:
  an asset with detections labeled outside `{dog, cat}` and no crop, asserting the new endpoint
  creates a real, correctable `Crop`/`CropClassification` -- matching #253's lesson that this exact
  kind of code path was previously "verified" by inspection alone and still shipped non-functional.

### Open questions
- Should the padding/box-expansion constants (`CropWriter(padding=0.15)`) be reused as-is for a
  manually-cropped box, or does a human-confirmed box deserve tighter/no padding since there's no
  detector-confidence uncertainty to hedge against? Default to reusing the existing constant unless
  a reviewer finds cropped context insufficient in practice.
- If the same photo has multiple crop-less detections overlapping the same physical animal (e.g. a
  dog detected once as `dog` with a crop, and separately as `sheep` with none), should mapping the
  second one warn about the likely duplicate? Out of scope for the first cut; revisit if duplicate
  identity examples from the same animal turn out to measurably affect classifier quality.

## Addendum: show classification type alongside identity (issue #263)

The identity text shown for a detection -- the box label on the photo and the row text in the list
below it -- previously showed only the identity or "Unknown", with no indication of what species it
was classified against. For a crop-less detection this could be actively confusing: an unidentified
detection with raw YOLO label `couch` showed the same bare "Unknown" as a genuine unidentified dog,
giving no hint that nothing had actually been mapped to a dog or cat yet. Both `PhotoLookupImage`'s
box label and `DetectionList`'s row text now append the detection's `species` in parentheses --
`"Fletch (dog)"`, `"Unknown (dog)"`, `"Unknown (couch)"` -- reusing the `species` field the lookup
endpoint already returns (the real crop species, or the raw YOLO label for a crop-less detection, per
the #261 addendum above) rather than adding a new field. A "not a dog or cat" detection is unchanged;
it keeps showing "Not a dog or cat" with no species suffix.

## Open questions
- None, other than the addenda above.
