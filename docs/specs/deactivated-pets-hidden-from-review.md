# Deactivated pets: keep classifications, hide from review

## Purpose

Make "Deactivate" mean *retire this pet from day-to-day review* without putting any of its
classification history at risk. Related: [v0.9.4 dynamic dog management](v0.9.4-dynamic-dog-management.md),
[ADR-001](../adr/ADR-001-state-database-source-of-truth.md).

## User story

As a pet owner, I want deactivating a dog or cat to keep all of its classifications and only hide
it from review, so that retiring a pet (or a duplicate or mistaken identity) never costs me
labeled photos or review work.

## Current behavior

Deactivating sets `Identity.is_active = False` (`DogService.set_active`). It deletes nothing, but:

| Area | Today |
| --- | --- |
| Existing classifications, review history, examples | Kept |
| Immich sync (tags and albums) | Unchanged; `is_active` is ignored |
| Classifier | Excludes the pet's examples (`classifier.py`, `reclassify.py`) |
| Reclassify | Re-scores every `AUTO` classification without the pet's examples, so a deactivated pet's auto-labels can be **silently reassigned to another pet or Unknown** |
| Review queue | Still shows pending items predicted as the pet |
| Pickers, Friends in Frame | Pet is hidden |

The reclassify row is the only way deactivation currently loses classifications.

## Goals

- A deactivated pet's classifications are never changed, reassigned, or removed by deactivation
  or by later reclassify runs.
- Pending review items for a deactivated pet no longer appear in any review view.
- Reactivating restores the previous state exactly.

## Non-goals

- Deleting a pet (separate from deactivating).
- Changing sync, tags, or albums for deactivated pets.
- Changing merge, which already leaves a deactivated tombstone.

## Requirements

- FR-1. Review queue, Grouped mode, and batch approval exclude unreviewed classifications whose
  identity is an inactive pet.
- FR-2. Reclassify skips `AUTO` classifications whose identity is an inactive pet, so they keep
  their identity, confidence, and status.
- FR-3. Deactivated pets still do not appear in identity pickers, and their examples are not used
  to classify new crops (unchanged).
- FR-4. The Library still shows and can filter by an inactive pet's photos, so the owner can
  find and correct them.
- FR-5. The deactivate confirmation and success message say that classifications are kept and
  only review is affected.

## Acceptance criteria

- Given a pet with pending review items, when I deactivate it, then those items disappear from
  Review and no classification row changes.
- Given a deactivated pet with `AUTO` classifications, when I run reclassify, then those rows are
  unchanged.
- Given I reactivate the pet, then its pending items return to Review.
- The confirmation text states that classifications are kept.

## Open questions

- Should reclassify also leave alone `AUTO` classifications that merely list an inactive pet as a
  *candidate*? Proposed: no, only the accepted identity is protected.
- Should deactivated pets' examples keep classifying new crops? Proposed: no, to match today.
  Say so if you would rather new photos of a retired pet still be matched.
