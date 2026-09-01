# Review Tab Engagement and Layout

## Purpose

The review tab is where reviewers spend most of their time in this app. Today the primary
controls (species correction, choose identity) sit in a single vertical column below the image,
so on a typical desktop viewport a reviewer has to scroll to reach them, and the "Similar memory"
reference image loads on every queue item whether or not the reviewer looks at it. Make the
desktop layout fit the image and the most-used controls in one screen, and make the repetitive
act of reviewing feel a little more rewarding without slowing it down.

## User Story

As a reviewer processing many photos in a row, I want the image and my most-used controls
(species, choose identity) visible together without scrolling, and I want small positive feedback
as I make progress, so that reviewing feels efficient and satisfying rather than tedious.

## Goals

- On desktop, the crop image and a consolidated action panel (prediction, species correction,
  choose identity, not-a-dog-or-cat) sit side by side, so both are visible together without
  vertical scrolling for typical desktop viewport heights.
- "Similar memory" becomes a collapsed-by-default section below the image/panel row; its
  reference image is only fetched once the section is expanded, avoiding an unnecessary image
  request on every queue item flipped through.
- A lightweight, non-blocking celebration marks every 10th reviewed classification, using the
  app's existing lifetime `reviewed` count (`/api/review/stats`) rather than new state, so the
  milestone is real progress rather than a per-session gimmick.

## Non-goals

- Persistent streaks, XP, points, badges, or leaderboards -- these need new backend-tracked state
  and are noted as a follow-up idea (see Open Questions), not built here.
- A broader visual redesign of the review page -- v1.2 already set the visual language; this spec
  only reorganizes existing panels and adds one small celebratory moment.
- Mobile/narrow-viewport layout changes beyond the responsive reflow the grid already provides.
  Below the two-column breakpoint the panel stacks under the image as it does today
  (ux-principles.md #15).

## Requirements

- The image and the action panel (prediction summary, species correction, choose identity,
  not-a-dog-or-cat) form a two-column layout at desktop widths (`lg` breakpoint), image on the
  left, panel on the right, per the request that "Species" and "Choose identity" move into the
  prediction panel and that panel move beside the image.
- All controls remain reachable by keyboard exactly as before (arrow keys, number keys, `S`) --
  the layout change must not alter `useReviewKeyboard` behavior.
- "Similar memory" is a collapsible section, collapsed by default. Its reference image element
  must not be present in the DOM (and therefore not requested) until the section has been
  expanded at least once; once expanded, it stays mounted so re-collapsing doesn't refetch it.
- The milestone celebration:
  - Triggers when the review queue's `reviewed` stat transitions to a positive multiple of 10
    after a review action (correct / skip / not-a-dog-or-cat), in the queue view only (the
    single-item edit view from the Library is a one-off correction surface, not the repetitive
    review flow this targets).
  - Is non-blocking: it does not steal focus, does not require dismissal, and disappears on its
    own after a couple of seconds.
  - Respects `prefers-reduced-motion` (ux-principles.md #14): reduced motion gets a simple fade,
    not a scale/bounce animation.
  - Is announced via an `aria-live="polite"` region for assistive technology, without interrupting
    the reviewer's keyboard flow.

## Acceptance Criteria

- On a desktop-width viewport, the review queue's image and its species/identity controls are
  visible without scrolling for a typical classification (no or few alternative candidates).
- Species correction and choose-identity actions live inside the panel beside the image, not
  below it in a separate full-width stack.
- Opening the review queue and flipping through several items without expanding "Similar memory"
  never requests `/api/embedding-examples/{id}/image`.
- Expanding "Similar memory" once for an item requests that item's reference image exactly once;
  collapsing and re-expanding does not request it again.
- Correcting, skipping, or marking not-a-dog-or-cat such that the lifetime reviewed count becomes
  a multiple of 10 shows the celebration; the next action (not a multiple of 10) does not.
- The single-item edit view (`?classification_id=`) never shows the milestone celebration.
- Existing keyboard shortcuts and review actions continue to work unchanged; existing tests pass.

## Open Questions

- Should milestone celebrations eventually track something more personal than the lifetime
  `reviewed` count -- e.g. a per-session count, or a persisted daily streak? That needs new
  backend state (a streak table, last-active-date tracking) and is out of scope here; worth its
  own spec if there's appetite for it.
- Other engagement ideas raised but not scoped into this spec: a review-velocity indicator
  ("12 in the last 5 minutes"), a richer end-of-queue celebration than today's "Review complete"
  empty state, and a subtle "on a roll" indicator for consecutive corrections that agree with the
  model's top prediction. None of these have a spec yet.
