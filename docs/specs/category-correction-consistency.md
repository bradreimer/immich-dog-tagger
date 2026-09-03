# Category Correction Consistency

## Purpose
A detection's category is one of four things: a named dog/cat identity, Unknown (no identity),
or Not a dog or cat. Today only three of those are things a reviewer can actively *choose* --
"Unknown" only ever appears as the fallback label shown when `identity` happens to be null; there
is no button or menu entry that sets it. Backend support already exists
(`ClassificationCorrectionService.correct()` accepts `identity=None` and settles it exactly like
any other human decision -- ReviewAction, forgetting any learning example), but the API's
`CorrectionRequest.identity` field is a required `str`, so nothing in the UI can reach that path.

On the Photo Lookup page specifically, the controls available to a detection also depend on its
*current* category instead of staying constant: once a detection is marked "Not a dog or cat",
its species buttons and identity selector disappear, leaving only "Undo" -- correcting a wrongly
flagged detection to a real dog/cat identity takes two round trips (Undo, then re-pick) instead of
one.

## User Story
As an owner correcting photos on the Photo Lookup page, I want "Unknown" to be a selectable
category everywhere species and identity corrections are offered, and I want to be able to
correct a detection currently in *any* category -- a named identity, Unknown, or Not a dog or
cat -- directly to any other category in a single action, so I don't have to guess an indirect,
multi-step workaround to fix a wrong call.

## Goals
- "Unknown" is an explicit, clickable correction option everywhere identity corrections are
  offered (Photo Lookup's per-detection controls, Review's identity chooser), not just a label
  shown when `identity` is already null.
- On Photo Lookup, every detection row exposes the full set of correction controls -- species
  buttons, identity/Unknown selector, Not-a-dog-or-cat toggle -- regardless of the detection's
  current category, so any category can be corrected to any other in one action.
- The correction API accepts an explicit "settle to Unknown" request, matching what the service
  layer already supports.

## Non-goals
- Changing Review's queue mechanics (Skip stays as is; it still just defers, it does not become a
  way to set Unknown).
- Adding categories beyond dog/cat identity, Unknown, and Not a dog or cat.
- Bulk/multi-select correction across several detections at once.

## Requirements
- `CorrectionRequest.identity` becomes optional (`str | None`) so a client can request Unknown
  explicitly; today it is a required `str`, which is the only thing currently blocking
  `ClassificationCorrectionService.correct()`'s existing `identity=None` path from the API.
- Photo Lookup's per-detection identity `<select>` (`DetectionList.tsx`) includes an "Unknown"
  option alongside the row's named identities, selectable regardless of the detection's current
  identity.
- Photo Lookup's species buttons and identity/Unknown selector (`DetectionList.tsx`) stay visible
  and usable when a detection is marked `not_animal`, instead of being replaced by a static
  species badge -- so correcting a wrongly-marked detection to a species + identity/Unknown is one
  action, not an Undo followed by a second correction.
- Choosing "Unknown" calls the same correction endpoint the identity buttons already use, with
  identity omitted/null, so it goes through the existing Unknown-settlement behavior (rescoring to
  no identity, forgetting any learning example for that crop, recording a `ReviewAction`).
- Review's identity chooser (`IdentityChooser.tsx`) gains the same explicit "Unknown" option, so
  the two correction surfaces stay consistent.

## Acceptance Criteria
- On Photo Lookup, a detection currently under a named identity can be corrected in one action to:
  Unknown, a different identity, the other species, or Not a dog or cat.
- On Photo Lookup, a detection currently marked Not a dog or cat can be corrected in one action
  directly to a species + identity/Unknown, without a separate Undo step first.
- On Photo Lookup, a detection currently Unknown can be corrected in one action to a named
  identity, the other species, or Not a dog or cat (already true today) and can also be
  re-confirmed as Unknown explicitly.
- Choosing Unknown on either Review or Photo Lookup produces the same result: no identity, no
  learning example for that crop, and a recorded `ReviewAction`.
- Existing species-only and not-animal-only corrections continue to work unchanged.

## Open Questions
- Library's per-item view routes corrections through Photo Lookup's "Edit Details" link rather
  than exposing its own controls -- confirm there's no separate Library-only correction surface
  that also needs the same treatment.
- Does removing the "hide controls while not_animal" gating affect existing
  `DetectionList`/`PhotoLookupPage` test fixtures that assert the static badge state?
