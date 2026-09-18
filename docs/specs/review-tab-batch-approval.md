# Review Tab Batch Approval

Tracking issue: TBD.

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

- **FR-1 -- Queue-wide grouping.** A new read builds clusters over the *entire active review
  queue*, not one pet at a time: for every identity that appears as the accepted prediction or a
  candidate on at least one active review-queue item, run the existing per-identity clustering
  (`RecommendationClusterService.clusters()`, unmodified) and concatenate the results into one
  list, sorted by group size (largest first) so the biggest throughput win surfaces first.
  Bounded the same way v1.8 already bounds a single identity's pool (`MAX_CANDIDATE_POOL`), plus
  a cap on the number of identities scanned per request; a request that hits the cap says so
  rather than silently truncating.
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
  approving, matching v1.8 FR-4 exactly (select-all/select-none, "Approve N photos" naming the
  count, empty selection disables approve). No new selection UI is invented -- reuse the existing
  cluster-card selection component.
- **FR-5 -- Reject a group.** "Not `<identity>`" rejects the group's members the same way
  `ClusterApprovalService.reject()` already does for the Library workspace, so a wrong grouping
  doesn't force a slow one-by-one skip.
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
- **FR-8 -- Keyboard support.** Grouped mode is keyboard-navigable: move focus between groups and
  members without a mouse, and trigger approve/reject on the focused group, consistent with
  ux-principles.md's keyboard-interaction expectations. This does not replace or alter
  `useReviewKeyboard.ts`'s existing Queue-mode bindings.

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
  mode.
- Existing Queue-mode tests, keyboard behavior, and `/review` API contracts are unchanged; new
  tests cover the queue-wide grouping query, per-member selection in Grouped mode, and the
  `reviewed`-count parity between the two modes.

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
