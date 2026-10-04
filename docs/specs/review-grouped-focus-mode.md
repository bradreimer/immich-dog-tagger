# Review Groups: One-at-a-Time Focus Mode

Tracking issue: [#366](https://github.com/bradreimer/immich-dog-tagger/issues/366). Refines
[review-tab-batch-approval.md](review-tab-batch-approval.md) (FR-3, FR-4, FR-8, FR-10) and keeps
[review-groups-temporal-spatial-refinement.md](review-groups-temporal-spatial-refinement.md)'s
default-deselection unchanged.

## Purpose

Grouped mode renders every proposed group as a stacked list of cards with 64px thumbnails and a
narrower set of actions than Queue mode (approve as the group's identity or a runner-up candidate,
"Not `<identity>`", or split). In practice that's hard to use:

- A long list of groups competes for attention; the reviewer can't focus on one decision.
- 64px thumbnails are too small to tell two similar-looking pets apart, which is the whole
  judgement a group approval depends on.
- A group that is the wrong species, or not an animal at all (a YOLO false positive cluster), has
  no bulk fix -- the reviewer has to split it and correct every member one by one.

## User story

As a reviewer using Grouped mode, I want to review one group at a time with large thumbnails and
the same choices Queue mode gives me (any identity, skip, wrong species, not a dog or cat), so I
can make a confident decision about the whole group without falling back to one-by-one review.

## Goals

- Show exactly one group at a time, with obvious Previous/Next navigation and a "Group X of N"
  position.
- Make member thumbnails 2-3x larger than today's 64px (at least 160px).
- Offer Queue mode's full choice set, applied to the group's selected members, using Queue mode's
  existing components (`IdentityChooser`, `SpeciesChooser`, `NotAnimalToggle`) so the two modes
  share one visual language.
- Keep Grouped mode's group-only actions: per-member selection, "Not `<identity>`", and "Review
  individually" (split).
- Reuse Queue mode's keyboard bindings with their Queue-mode meanings.

## Non-goals

- No backend or API changes. Every action reuses an existing endpoint.
- No change to how groups are built, sorted, or refined (`ReviewGroupingService`).
- No change to Queue mode or the split view.

## Requirements

- **FR-1 -- One group at a time.** Grouped mode shows a single group. Previous/Next buttons and a
  "Group X of N" label move between groups without writing anything. After an action settles a
  group, the list is refetched and the reviewer stays at the same position, which now shows the
  next group (clamped to the last group).
- **FR-2 -- Larger thumbnails.** Member thumbnails render at least 160px square (2.5x the previous
  64px), in a responsive grid beside the action panel on desktop and above it on narrow screens.
- **FR-3 -- Choose identity.** The action panel reuses `IdentityChooser`, listing every active
  identity of the group's species, with the group's identity starred as predicted. Choosing the
  group's own identity approves the selection (`approveCluster`); choosing any other identity
  reassigns it (`reassignCluster`, issue #166). This subsumes FR-10's runner-up buttons.
- **FR-4 -- Skip.** Skip records a skip for each selected member (`POST /review/{id}/skip`), the
  same write Queue mode's Skip makes.
- **FR-5 -- Wrong species.** `SpeciesChooser` corrects each selected member's species
  (`POST /classifications/{id}/species`).
- **FR-6 -- Not a dog or cat.** `NotAnimalToggle` marks each selected member's crop as not an
  animal (`POST /crops/{id}/not-animal`).
- **FR-7 -- Group-only actions stay.** Per-member selection (select all/none, mismatch members
  start deselected), "Not `<identity>`" (`rejectCluster`), and "Multiple `<dogs/cats>` here? Review
  individually" (split view) remain.
- **FR-8 -- Keyboard.** Queue mode's bindings apply to the current group: `1`-`9` choose an
  identity for the selection, `S` skips the selection, and the arrow keys move to the previous/next
  group. Replaces the parent spec's FR-8, which kept the group list keyboard-free because a list
  had no single "current" group.
- **FR-9 -- Stale members.** Per-member actions (FR-4 to FR-6) skip a member whose classification
  or crop no longer exists, and the result message reports how many were skipped, matching how
  the split view handles stale items (issue #356).
- **FR-10 -- Stats.** Every action that settles members (FR-3 to FR-6) refreshes the lifetime
  `reviewed` stat; "Not `<identity>`" still does not, per the parent spec.
- **FR-11 -- View in Immich.** Each member thumbnail has the same "View in Immich" link Queue
  mode shows (`ImmichPhotoLink`), opening the original photo in a new tab. It sits outside the
  select button, so following it never changes the selection, and is omitted when the Immich URL
  or asset id is unknown (issue #403).
- **FR-12 -- Date range.** The group header shows the earliest and latest capture dates of its
  members (`cluster.earliest_captured_at` / `latest_captured_at`): a single date when equal,
  nothing when no member is dated (issue #403).

## Acceptance criteria

- Grouped mode shows one group, a "Group X of N" label, and Previous/Next controls; the arrow keys
  do the same.
- Thumbnails are at least 160px square.
- Choosing the starred identity calls `approveCluster` with the selected ids; choosing any other
  identity calls `reassignCluster`.
- Skip, species correction, and "Not a dog or cat" apply to exactly the selected members.
- Every action is disabled when nothing is selected, except navigation and split.
- After an action, the reviewer lands on the next group without scrolling.
- Existing split-view behavior and tests are unchanged.

## Open questions

- A server-side batch endpoint for skip/species/not-animal would make those actions atomic. Left
  out while groups stay small (bounded by `MAX_CANDIDATE_POOL`); revisit if latency is noticeable.

## Status

- FR-1 through FR-10 -- implemented in `ReviewGroupedPanel.tsx` and `ReviewGroupCard.tsx`
  (issue #366).
- FR-11, FR-12 -- implemented in `ReviewGroupCard.tsx` (issue #403); no backend change.
