# DT-1115: Fix "N images need review" banner promising work the Review queue doesn't have

## **ID**

DT-1115

## **Related spec**

None -- bug fix, not new behavior.

## **Priority**

High

## **Status**

Completed

## **Goal**

Fix a mismatch reported in production: Mission Control's next-action banner and the sidebar's
"Review" nav badge said "77 images need review," but navigating to the Review page showed "No
classifications need attention right now" -- an empty queue. Any UI element that tells the owner
"N images need review" must promise exactly what clicking through to Review actually delivers.

## **Context**

Reported live (via a real deployment, not a test): the banner text and the Review page's empty
state disagreed about whether there was work to do.

Root cause: `ReviewQueryService.review_queue_stats()` (`services/review_query.py`) computed its
`remaining` field as `total - reviewed` -- every classification without an explicit `ReviewAction`,
including ones that are confidently auto-classified and were never actually going to need a human
to look at them. `GET /review/stats` (`api/routes/review.py`) exposes this field directly, and it's
consumed by `ui/src/components/layout/Sidebar.tsx`'s nav badge, `ui/src/features/overview/OverviewPage.tsx`'s
"Review Remaining" stat tile and next-action banner (DT-1106), and `ReviewPage.tsx`'s own progress
bar -- all via `getReviewStats()`.

Meanwhile `GET /review` itself is backed by `ReviewQueryService.active_review()`, which only
returns items with no review action AND (unknown OR below the confident threshold) -- exactly
matching the already-existing `ReviewQueryService.review_queue_count()`, whose docstring even
already contrasted itself against `review_queue_stats().remaining` by name: "Unlike
`review_queue_stats().remaining` (total minus reviewed), this excludes confidently-classified items
that simply haven't been manually reviewed yet." DT-1102 introduced `review_queue_count()` and
wired it into `GET /metrics`'s `review_queue_size` for exactly this reason, but never updated
`review_queue_stats().remaining` itself -- so the stale, pre-DT-1102 definition was still live at
`GET /review/stats`, and DT-1106 (added afterward) innocently consumed that stale field for its new
banner, reintroducing the exact inconsistency DT-1102 had already fixed elsewhere.

## **Implementation notes**

- `services/review_query.py`: `review_queue_stats().remaining` now returns
  `self.review_queue_count()` instead of `total - reviewed`. `total` and `reviewed` are unchanged
  and still accurate on their own; only what "remaining" means changed, to match what `/review`
  actually returns everywhere it's surfaced. Updated `review_queue_count()`'s docstring, which no
  longer contrasts itself against a different value once `review_queue_stats()` reuses it.
- No frontend changes needed -- `Sidebar.tsx`, `OverviewPage.tsx`, and `ReviewPage.tsx`'s
  `ReviewProgress` all consume `getReviewStats().remaining` already; fixing the field at its one
  source fixes every caller.

## **Acceptance criteria**

- `GET /review/stats`'s `remaining` equals the number of items `GET /review` actually returns for
  the same database state.
- A confidently-classified classification with no review action does not count toward `remaining`.
- Live-verified: seeded 77 confidently-classified, unreviewed classifications against a running API
  instance -- `GET /review/stats` now reports `remaining: 0` (previously `77`), matching `GET
  /review`'s empty result, reproducing and resolving the exact reported scenario.

## **Testing requirements**

- `tests/test_review.py::test_review_queue_stats_remaining_matches_review_queue_count` -- seeds one
  confidently-classified and one needs-review classification, asserts `remaining == 1` (not the
  `total - reviewed` value of `2`) and `remaining == review_queue_count() == len(active_review())`.
- `tests/api/test_review.py::test_review_stats_remaining_excludes_confidently_classified_items` --
  same scenario through `GET /review/stats` and `GET /review` together.
- Removed the old `test_review_stats` assertion that `remaining == total - reviewed` -- that was
  the bug's invariant, not a real contract.
- Full `./scripts/check.sh` passes.

## **Dependencies**

None.

## **Suggested commit message**

`fix(DT-1115): make review_queue_stats().remaining match what GET /review actually returns`
