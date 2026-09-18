# Review Tab Batch Approval

Tracking issue: [#333](https://github.com/bradreimer/immich-dog-tagger/issues/333).

## Purpose

The review queue is a large, growing backlog (thousands of items) worked one photo at a time
(`ReviewPage.tsx`, `useReviewKeyboard.ts`): correct, skip, or mark not-an-animal, then the next
item. Throughput is capped at one decision per photo no matter how visually repetitive the queue
is -- ten near-identical photos of the same dog from the same walk cost ten decisions.

v1.8.0 already solved exactly this problem once: `RecommendationClusterService` groups one
identity's pending candidates into visually-similar clusters over their existing embeddings, and
`ClusterApprovalService` settles a whole cluster as N ordinary corrections in one action. It was
built, tested, and shipped -- then [ADR-008](../adr/ADR-008-library-flat-browse-workspace.md)
removed its only UI entry point (the Library page's pet-first workspace) because forcing an owner
to pick a pet before seeing anything was the wrong default for *browsing/auditing* the catalogue.
That critique doesn't apply to the *review queue*: a reviewer opening `/review` already wants to
process pending items, not audit by an arbitrary axis, so there is no pet-first gate to object to.

This spec reuses that existing, tested backend from inside the Review tab itself -- not a new
page or tab -- so a reviewer can clear a batch of similar predictions in one action without
leaving the workflow they already use.

## User story

As a reviewer facing a large backlog, I want to see and approve groups of visually similar
pending photos together from the Review tab, so my throughput scales with how many distinct
groups are in the queue rather than with how many photos are in it.

## Goals

- Add a **Grouped** view mode to the existing `/review` tab, alongside today's one-at-a-time
  **Queue** mode. Same page, same URL, a mode toggle -- not a new tab or route.
- Grouped mode clusters the *active review queue's* pending items -- across every identity that
  currently has queue items, not one pet selected up front -- by predicted identity and then by
  visual similarity, reusing `agglomerative_clusters`/`RecommendationClusterService`'s existing
  algorithm unchanged.
- Approving or rejecting a group writes through the same paths Queue mode already uses
  (`ClassificationCorrectionService.correct()` via `ClusterApprovalService`), so every correction
  looks identical in provenance, learning examples, and the next sync's album reconciliation,
  whether it came from Queue or Grouped mode.
- Preserve per-member control (deselect the odd photo out) exactly as v1.8 FR-4 already built it,
  so an impure cluster doesn't force an all-or-nothing choice.
- Give the reviewer an explicit way out when a group is *wrong* -- not just impure, but actually
  spanning more than one individual (two similar-looking dogs the clustering couldn't tell
  apart) -- by dropping straight into reviewing that group's members one at a time, rather than
  forcing either a bad bulk approval or an all-or-nothing reject.
- Keep Queue mode as the default and completely unchanged: Grouped mode is additive, and a
  reviewer who never touches the toggle sees no behavior change.

## Non-goals

- **Not a fix for the "Unknown" bucket.** Grouping requires an existing predicted identity or
  candidate to group by; a classification with no prediction (`identity IS NULL`) has nothing to
  cluster against and stays in Queue mode, exactly as v1.8's FR-7 decided for the Library
  ("cold start stays the Review tab's job"). Grouped mode targets the "review queue" count, not
  the "unknown" count.
- Reviving the Library page's pet-selector workspace. That UI stays retired per ADR-008; this
  spec's grouping is queue-driven and automatic, with no pet-selection step to object to.
- Changing classification policy, thresholds, or the clustering algorithm/distance cut.
- Gamification (streaks, XP, badges, leaderboards). Already scoped out by
  [review-tab-engagement-and-layout.md](review-tab-engagement-and-layout.md) as needing new
  backend state; unaffected by this spec.
- A new keyboard vocabulary. Grouped mode reuses `useReviewKeyboard.ts`'s existing keys and the
  toggle-button selection pattern v1.8 FR-4 already established (no second keymap).

## Requirements

- **FR-1 -- Queue-wide grouping.** A new read (`ReviewGroupingService`) builds clusters over the
  *entire active review queue*, not one pet at a time: for every identity that appears as the
  accepted prediction or a candidate on at least one active review-queue item, run the existing
  per-identity clustering (`RecommendationClusterService.clusters()`/`clusters_in_pool()`) and
  concatenate the results into one list, sorted by group size (largest first) so the biggest
  throughput win surfaces first. Every identity of the same species shares one candidate-pool
  scan (`pending_pool()`), fetched once and sliced per identity, rather than each identity
  re-running its own full-species scan -- on a library with a few thousand pending candidates
  across many identities, the per-identity re-scan was what made loading or refreshing Grouped
  mode take 30+ seconds (issue #334). A cluster of exactly one photo is excluded -- it has no
  batching benefit over correcting it from Queue mode, so Grouped mode only ever shows a group
  that actually saves the
  reviewer decisions. Bounded the same way v1.8 already bounds a single identity's pool
  (`MAX_CANDIDATE_POOL`), plus a cap on the number of identities scanned per request
  (`MAX_GROUP_IDENTITIES`); a request that hits either cap says so rather than silently
  truncating.
- **FR-2 -- Mode toggle on `/review`.** A "Queue" / "Grouped" toggle sits beside the existing
  filter buttons (`all` / `unknown` / `low-confidence` / `candidate-conflict`). Switching modes
  does not navigate away from `/review`. Queue mode is the default on load; the last-chosen mode
  is not required to persist across sessions.
- **FR-3 -- Approve a group.** Each group shows a representative crop, member count, confidence
  range, and capture-date range (the same `RecommendationCluster` fields v1.8 already returns).
  Approving applies the predicted identity to every selected member via
  `ClusterApprovalService.approve()` -- N ordinary corrections, same provenance as N single
  corrections from Queue mode.
- **FR-4 -- Per-member selection.** Members start selected; any member can be deselected before
  approving, matching v1.8 FR-4's convention (select-all/select-none, "Approve N photos" naming
  the count, empty selection disables approve). Grouped mode's cluster card is a new, self-
  contained component (`ReviewGroupCard`) rather than a shared one -- no Library cluster-card
  component exists to reuse today (ADR-008 retired that UI along with its components, keeping
  only the backend) -- but the interaction it presents is the same one v1.8 established.
- **FR-5 -- Reject a group.** "Not `<identity>`" rejects the group's members the same way
  `ClusterApprovalService.reject()` already does for the Library workspace, so a wrong grouping
  doesn't force a slow one-by-one skip.
- **FR-9 -- Split a mixed group into individual review.** Every group carries a "Multiple
  `<dogs/cats>` here? Review individually" action, independent of the selection checkboxes.
  Choosing it drops the group's members into a mini one-at-a-time queue, reusing `ReviewCard` and
  `useReviewKeyboard` exactly as Queue mode does -- same identity chooser (every identity of that
  species, not just the one the group was clustered under), same correct/skip/species-correction/
  not-animal actions, same keyboard bindings. This is the answer to a cluster that isn't just
  impure (FR-4 handles that) but wrong at the grouping level: two individuals the embeddings
  couldn't tell apart. No new write path -- every action here is the identical
  `POST /classifications/{id}/correct`-family call Queue mode already makes. Finishing or backing
  out of the split view returns to the group list, which is refetched so a partially-settled
  group reflects what was just done.
- **FR-6 -- Queue accounting stays correct.** Approving or rejecting a group updates the review
  queue count and the Grouped-mode list the same way a Queue-mode correction updates the
  one-at-a-time queue -- a settled item disappears from both modes' view of the backlog, and the
  sidebar/Overview "N need review" figures reflect it immediately.
- **FR-7 -- Milestone celebration counts members, not groups.** The existing "every 10th
  reviewed" celebration
  ([review-tab-engagement-and-layout.md](review-tab-engagement-and-layout.md)) keys off the
  lifetime `reviewed` stat. A group approval of N members must advance that stat by N, the same
  as N individual corrections would, so the milestone and every count derived from `reviewed`
  stay accurate regardless of which mode produced them.
- **FR-8 -- No new keyboard vocabulary.** Grouped mode's own list (approve/reject/select a group)
  is a normal tabbable button list -- standard browser tab/click/space/enter semantics, no bespoke
  keymap. `useReviewKeyboard.ts`'s existing bindings (arrows, `S`, number keys) are unchanged and
  are not wired into the group list, so Queue mode's muscle memory is never at risk of firing an
  unexpected group action. The one place Grouped mode *does* get full keyboard support is FR-9's
  split view, which is Queue mode's own component and keymap reused as-is. A dedicated keyboard
  scheme for navigating the group list itself is left as an open question rather than built here.
- **FR-10 -- Approve a group as an alternate top-predicted identity (issue #335).** A group is
  visually correct far more often than its clustered-under identity is right -- the classifier's
  top pick for the cluster is sometimes the wrong dog even though a runner-up candidate on the
  representative photo is correct. Alongside "Approve N as `<identity>`", the group card shows one
  "Approve N as `<candidate>`" action per other identity in the representative member's stored
  top-`policy.candidate_limit` candidates (deduplicated, excluding the group's own identity).
  Choosing one reassigns exactly the selected members to that identity via
  `ClusterApprovalService.reassign()`/`POST /library/clusters/reassign` -- the same write path
  issue #166 already built for the Library's single-pet cluster view, which does not require the
  classifier to have proposed that identity for every member, unlike plain `approve()`. A group
  whose representative has no alternate candidates shows no extra buttons.

## Acceptance criteria

- Opening `/review` shows Queue mode by default, unchanged from today; switching to Grouped mode
  and back loses no in-progress Queue-mode state.
- Grouped mode lists clusters spanning every identity with pending review-queue items, not just
  one selected pet; a queue with items for three different dogs shows groups for all three
  without any pet-selection step.
- Approving a group of N members produces exactly N `ReviewAction` rows and N corrections with
  the same provenance as N Queue-mode corrections; the review-queue count drops by N immediately
  after.
- Deselecting a member before approving excludes exactly that member; approving with every member
  deselected is refused by the UI and, if attempted directly, by the API.
- A classification with no predicted identity or candidates never appears in Grouped mode and
  remains reachable only through Queue mode.
- The lifetime `reviewed` count and its milestone celebration advance identically whether N items
  were corrected one at a time in Queue mode or in a single N-member group approval in Grouped
  mode; rejecting a group does not change the `reviewed` count, since a rejection settles no
  identity (same rule as the Library workspace's reject).
- Choosing "Review individually" on a group steps through its members one at a time with the
  full Queue-mode correction surface and keyboard bindings; correcting a member there is an
  ordinary correction indistinguishable in provenance from one made through Queue mode or a group
  approval; finishing or leaving the split view returns to an up-to-date group list.
- Approving a group as an alternate candidate identity (FR-10) applies exactly that identity to
  every selected member, updates the reviewed stat by that many, and never duplicates the group's
  own identity among the offered alternates; a group whose representative has no alternates shows
  no extra approve buttons.
- Loading Grouped mode, and refreshing it after an approve/reject action, stays interactive on a
  library with several thousand pending candidates spread across many identities (issue #334).
- Existing Queue-mode tests, keyboard behavior, and `/review` API contracts are unchanged; new
  tests cover the queue-wide grouping query (including singleton-cluster exclusion and the
  identity cap), per-member selection and approve/reject in Grouped mode, the split-into-
  individual-review flow, and the `reviewed`-count parity between the two modes.

## Open questions

- Should Grouped mode become the default view once a reviewer's backlog exceeds some size, or
  stay an opt-in toggle indefinitely? Left to usage feedback rather than decided here.
- Should a rejected group's members be excluded from Grouped mode for some cooldown period so a
  bad grouping doesn't reappear immediately, or is falling back to Queue mode for them sufficient?
- Extending clustering to `identity IS NULL` items via embedding similarity alone (bootstrap
  clusters with no predicted label yet) would help the "Unknown" bucket specifically, but is a
  meaningfully different mechanism (grouping without a candidate identity to anchor confidence or
  the approval write). Left out of this spec, as v1.8 FR-7 left cold start out of its own.
- Gamification beyond the existing milestone celebration is tracked separately in
  [review-tab-engagement-and-layout.md](review-tab-engagement-and-layout.md)'s open questions, not
  here.
- A dedicated keyboard scheme for moving between groups/members in the group list itself (FR-8)
  is left for a follow-up if reviewers want it -- today the list is mouse/tab driven, and only the
  FR-9 split view carries the full keyboard vocabulary.

## Status

- FR-1 through FR-10 -- implemented. `services/review_groups.py` (`ReviewGroupingService`),
  `services/clusters.py` (`pending_pool()`/`clusters_in_pool()`, issue #334),
  `GET /review/groups`, `ui/src/features/review/components/ReviewGroupedPanel.tsx`,
  `ReviewGroupCard.tsx`, and `ReviewGroupSplitView.tsx`.
