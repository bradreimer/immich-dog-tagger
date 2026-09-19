# Review Groups: Temporal/Spatial Refinement

Tracking issue: TBD (see [review-tab-batch-approval.md](review-tab-batch-approval.md) for the
parent Grouped mode spec this refines).

## Purpose

Grouped mode's clusters ([review-tab-batch-approval.md](review-tab-batch-approval.md), FR-1) are
built by `ReviewGroupingService`/`RecommendationClusterService` from raw embedding similarity
alone: `proposes_identity()` pools any pending classification where an identity appears *anywhere*
in its stored candidates, then `agglomerative_clusters()` groups those crops by visual distance.
Whether that identity is actually the member's highest-ranked prediction is never checked.

The classifier already computes a stronger signal for exactly this: each candidate carries
`temporal_weight`/`spatial_weight` (ADR-003, ADR-007) reflecting how well its capture date and
location align with the photo being classified, `candidates` is sorted by `weighted_score`
(`similarity * temporal_weight * spatial_weight`, `classifier.py`), and `ReviewQueryService`
already surfaces `temporal-mismatch`/`location-mismatch` reasons for Queue mode from the same
data. Grouped mode ignores all of it: a photo can land in "Rex"'s visual cluster because it looks
like Rex, while its own top-ranked (time/location-weighted) prediction is actually "Max," a
visually similar dog photographed at a different time or place. Bulk-approving that group's
default selection would misassign that photo to Rex.

## User story

As a reviewer using Grouped mode, I want a group to only default-include photos where the group's
identity is genuinely each photo's top prediction -- not just a photo that happens to look
similar -- so approving a group in one action can't silently misassign a look-alike dog's or
cat's photo the way a purely visual grouping can.

## Goals

- Keep visual clustering (`agglomerative_clusters`, the existing distance threshold) exactly as
  it is today -- this is a second pass over its output, not a replacement.
- After clustering, check each member against the group's identity using the same signal already
  computed for it: the member's top-ranked candidate (`candidates[0]`, already sorted by
  `weighted_score`, which already folds in `temporal_weight`/`spatial_weight`). A member whose
  top-ranked identity is not the group's identity is flagged as a refinement mismatch.
- A flagged member stays visible in the group (so the reviewer still sees where it went) but
  starts **deselected**, the same per-member selection mechanism FR-4 of the parent spec already
  built for an impure cluster -- no new selection UI, no new write path. Approving the group's
  default selection therefore never includes it.
- Label a flagged member with the same reason vocabulary Queue mode already shows
  (`temporal-mismatch` / `location-mismatch`, from `ReviewQueryService._review_reason()`), so a
  reviewer who already recognizes those labels from Queue mode reads the same thing here.
- Reuse the existing mismatch thresholds (`_TEMPORAL_MISMATCH_THRESHOLD` /
  `_SPATIAL_MISMATCH_THRESHOLD`, currently 0.5) rather than inventing new ones -- refinement
  should agree with what Queue mode already calls a mismatch, not apply a second, different
  standard for the same underlying weights.
- A group with every member flagged is still shown (so the reviewer isn't left wondering where a
  visually tight cluster went) but approving it is refused the same way an empty selection already
  is (parent spec's acceptance criteria).

## Non-goals

- Not changing what makes two photos visually similar enough to cluster (distance threshold,
  `agglomerative_clusters` algorithm) -- refinement only affects which members are pre-selected
  within a cluster that's already formed.
- Not recomputing or re-deriving `temporal_weight`/`spatial_weight` -- reuse `scoring.py`'s
  existing functions and the weights already stored on `CropClassification.candidates`. No new
  classifier pass.
- Not changing `_TEMPORAL_MISMATCH_THRESHOLD`/`_SPATIAL_MISMATCH_THRESHOLD` or the underlying
  `TEMPORAL_SIGMA_DAYS`/`SPATIAL_SIGMA_KM`/`*_FLOOR` constants -- that's classifier policy tuning,
  a separate concern from how Grouped mode presents an existing signal.
- Not touching Queue mode, which already has its own (unclustered) temporal/spatial mismatch
  handling.
- Not extending grouping to `identity IS NULL` ("Unknown") items -- still out of scope, per the
  parent spec's own non-goal.
- Not a new bulk action. FR-10's "Approve as `<candidate>`" already exists for a member whose top
  candidate differs from the group's identity; refinement decides this feature's *default
  selection*, it doesn't add another approval path.

## Requirements

- **FR-1 -- Per-member refinement check.** For each member of a proposed cluster, compare the
  group's identity against that member's `candidates[0].identity` (its weighted-score-ranked top
  prediction). A match is unflagged; a mismatch is flagged, carrying whichever of
  `temporal-mismatch`/`location-mismatch` applies -- the same precedence Queue mode's
  `_review_reason()` already uses (temporal checked first) -- or a generic "different top
  prediction" reason if neither weight crosses its threshold but the identity still differs.
- **FR-2 -- Flagged members start deselected.** `ReviewGroupCard`'s selection state initializes
  flagged members to unselected and unflagged members to selected (unchanged default), reusing
  FR-4's existing selection mechanism -- no new component, no new API field beyond what carries the
  flag itself.
- **FR-3 -- Reason surfaced in the UI.** A flagged member shows the same badge/label Queue mode
  already renders for `temporal-mismatch`/`location-mismatch`, so the vocabulary a reviewer learns
  in one mode transfers to the other.
- **FR-4 -- Group approval unaffected in mechanism.** `ClusterApprovalService.approve()` still
  operates purely on whatever the current selection is; refinement only changes what that
  selection defaults to, not how approval itself works. Flagged members can still be manually
  selected and approved if the reviewer disagrees with the flag -- refinement is a default, not a
  restriction.
- **FR-5 -- All-flagged groups stay visible, refused on approve-all.** A cluster where every
  member is flagged still appears in the group list (it may still be worth a "Review individually"
  split per the parent spec's FR-9); approving it with the default (empty) selection is refused
  the same way an empty selection already is.
- **FR-6 -- No behavior change when weights are absent.** Per `scoring.py`'s fail-open contract,
  a member with no capture date or no coordinates on either side already carries
  `temporal_weight`/`spatial_weight` of `1.0` and is never flagged for that dimension --
  refinement inherits this for free by reusing the stored weights rather than re-deriving them.

## Acceptance criteria

- A visually clustered group whose members all agree with the group's identity on top-ranked
  prediction behaves exactly as it does today: all members selected by default.
- A group containing a member whose top-ranked prediction differs from the group's identity shows
  that member deselected by default, labeled with the applicable mismatch reason, and still
  individually selectable.
- Approving a group's default selection never applies the group's identity to a flagged member
  that the reviewer didn't explicitly re-select.
- A group where every member is flagged is refused on approve with no selection, matching the
  existing empty-selection refusal (UI and API).
- Members with missing capture date or coordinates are never flagged for that dimension, matching
  `scoring.py`'s fail-open behavior.
- New tests cover: a mismatched member flagged and deselected by default, a flagged member
  remaining independently selectable and approvable, an all-flagged group refusing an empty-
  selection approve, and fail-open behavior for missing date/location data -- alongside the
  existing Grouped-mode test suite (`tests/test_review_groups.py`), which stays green unchanged
  for the all-agree case.

## Open questions

- Should the refinement flag also suppress a flagged member from FR-10's "Approve N as
  `<candidate>`" default when the candidate it names is itself mismatched, or is that already
  covered by FR-10 only offering identities the member's own candidates actually contain? Left to
  implementation -- FR-10 already operates per-member.
- Should a flagged member's badge link directly into FR-9's split-into-individual-review flow for
  that one photo, rather than requiring the reviewer to split the whole group? Deferred as a UI
  refinement, not required for the core behavior above.
