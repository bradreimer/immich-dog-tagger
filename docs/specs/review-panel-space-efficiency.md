# Review Panel Space Efficiency

## Purpose

[review-tab-engagement-and-layout.md](review-tab-engagement-and-layout.md) moved the review
queue's prediction/species/identity/not-a-dog-or-cat controls into a column beside the crop image
so both are visible without scrolling. In practice the two columns rarely end up the same height:
the action column (four stacked cards) is almost always taller than the image, and the grid aligns
both columns to the top, so the image column ends in a large empty gap down to the "Similar
memory" section below. The action column itself also spends more height than it needs to, since
each of "Wrong species?" and "Not a dog or cat?" -- both low-frequency edge-case corrections -- is
its own full card with its own header and padding. Tighten the layout so the space that spec
claimed is actually used.

## User Story

As a reviewer using the review queue on a desktop-width viewport, I want the image and action
panel to fill their shared row without a large empty gap, and the less-used correction controls to
take up less space, so the panel feels intentionally laid out rather than leaving visible dead
space.

## Goals

- The image column and the action column fill the same visual height in their grid row (no
  large empty gap below a short image next to a tall action column).
- "Wrong species?" and "Not a dog or cat?" -- both infrequent, edge-case corrections -- are
  visually consolidated so they cost one card's worth of chrome (header + padding) instead of two,
  shrinking the action column's total height.
- The review page (queue view and the single-item `?classification_id=` edit view) also exposes
  "View in Immich" and "Edit Details" links, matching the Library page's Details panel.

## Non-goals

- No change to which controls exist or what they do -- Species correction, choose identity, skip,
  and not-a-dog-or-cat all keep their current behavior, keyboard shortcuts, and accessible names.
- No change to the "Similar memory" collapsible section or the milestone celebration introduced by
  review-tab-engagement-and-layout.md.
- No mobile/narrow-viewport layout changes -- below the two-column breakpoint the panel continues
  to stack under the image.

## Requirements

- The review card's two-column grid (`ReviewCard.tsx`) stretches both columns to the row's height
  at the `lg` breakpoint instead of aligning them to the top, so the image's card fills the same
  height as the action column rather than leaving blank space beneath a short image.
- The crop image continues to use `object-contain` so it is never cropped or distorted -- letting
  its card stretch only changes how much of the taller column's height that card's background
  fills, not how the image itself is scaled or cropped.
- "Wrong species?" and "Not a dog or cat?" render inside one shared, compact card instead of two
  separate cards, without changing either control's accessible name, click behavior, or the
  `role="group"`/`aria-label="Correct species"` grouping on the species buttons.
- `ReviewCard` already renders "View in Immich" (`ImmichPhotoLink`) and "Edit Details"
  (`PhotoLookupLink`) beside the reason/date on every review item, in both the queue view and the
  single-item edit view -- confirmed present and covered by `ReviewCard.test.tsx`; no functional
  gap here, just verification.

## Acceptance Criteria

- On a desktop-width viewport, for a landscape/wide crop whose natural height is much shorter than
  the action column, the image's card visibly fills the row height (no large empty gap between the
  bottom of the image card and the "Similar memory" section).
- "Wrong species?" and "Not a dog or cat?" appear inside a single card in the action column.
- All existing `ReviewCard`/`ReviewPage` tests continue to pass unmodified in behavior (button
  names, link hrefs, `role="group"` species buttons) -- only the container structure changes.
- `View in Immich` and `Edit Details` links are present on both `/review` (queue) and
  `/review?classification_id=` (single-item edit) views.

## Open Questions

- None -- this is a layout-only tightening of an already-shipped panel.
