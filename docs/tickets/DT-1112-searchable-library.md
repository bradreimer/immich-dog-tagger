# DT-1112: Searchable library of classified photos

## **ID**

DT-1112

## **Related spec**

[v1.4-trustworthy-photo-library.md](../specs/v1.4-trustworthy-photo-library.md) (FR-2)

## **Priority**

High

## **Status**

Completed

## **Goal**

Add a persistent, searchable/filterable library of every classified photo -- reviewed and
unreviewed alike -- as a new primary surface, alongside (not replacing) the existing Review queue.
This is the concrete UX shift the interview identified: the owner's mental model is "browse and
maintain a library," not "clear a queue that empties out and disappears."

## **Context**

Today there is no way to see a classified photo once it's no longer in the active review queue.
`ReviewQueryService` (`src/immich_dog_tagger/services/review_query.py`) has exactly two read
paths, both queue-shaped:

- `classifications()` (line 89) -- supports `identity`, `unknown`, `confidence_below`, `limit`
  filters, but no `offset`/pagination and no date-range or review-status filter. It's used
  internally by other services, not exposed as a general browse API.
- `active_review()` (line 209) -- the actual `GET /review` queue: `~self._has_review_action()` is
  a hard `WHERE` clause (line 234), so anything already reviewed is permanently excluded from
  every response this method can produce. There is no code path today that returns a reviewed
  item once it's been acted on.

`_has_review_action()` (line 322) already correctly determines review status via `ReviewAction`
existence -- reuse it for the library's review-status filter rather than reimplementing it.

`api/routes/review.py` has three routes (`GET /review`, `GET /review/stats`,
`POST /review/{id}/skip`), all queue-scoped. There is no `api/routes/library.py` or equivalent.

## **Implementation notes**

- **Backend**: add a `library()` method to `ReviewQueryService` (reusing `_to_review_item()`,
  `_REVIEW_ITEM_RELATIONSHIPS`, and the DT-1111 `captured_at` field once that ships) that:
  - Does **not** filter out reviewed items -- the entire point is to show everything.
  - Accepts `identity`, `species`, `reviewed: bool | None` (using `_has_review_action()`),
    `captured_after`/`captured_before` (filtering on `Asset.captured_at`, joined the same way
    DT-1111 already needs), and `limit`/`offset` for pagination.
  - Returns a small `LibraryPage` dataclass: `items: list[ReviewItem]`, `total: int`, `limit: int`,
    `offset: int` -- `total` needs a separate `COUNT(*)` query with the same filters applied
    (mirroring the existing `select(func.count())...` pattern already used in
    `review_queue_stats()`), not `len(items)`, since `items` is a page, not the full result set.
  - Also return, per item, whether it's been reviewed and the most recent `ReviewAction`'s
    `created_at` (so the library can show "reviewed 3 days ago" the way an actual library
    catalogue would) -- add `reviewed: bool` and `reviewed_at: datetime | None` to `ReviewItem`
    or a thin wrapper around it, whichever keeps `ReviewItem` from growing fields the queue view
    itself doesn't use. A wrapper (`LibraryEntry(item: ReviewItem, reviewed: bool, reviewed_at:
    datetime | None)`) keeps the distinction explicit.
  - New `api/routes/library.py`: `GET /library` with the above query params, `response_model` built
    the same way `review.py`'s routes are (explicit response construction, not a raw ORM/dataclass
    return -- see DT-1109 for why that matters). Register it in `api/app.py` alongside the other
    routers.
- **Frontend**: new `ui/src/features/library/` feature (mirroring the `review/`/`dogs/` feature
  folder structure): a `LibraryPage.tsx` with a filter bar (identity dropdown reusing the same
  `getDogs()` call other pages already use, species toggle, reviewed/unreviewed toggle, date
  range) and a paginated grid/list of results, each showing the photo, species, predicted/current
  identity, confidence, capture date (DT-1111), and reviewed status.
  - Add a new `getLibrary(query)` function to `ui/src/lib/api.ts` following the existing
    `getReview(query)` pattern.
  - Add a new sidebar nav entry ("Library") in `ui/src/components/layout/Sidebar.tsx`'s `links`
    array, alongside the existing five. (See the spec's Open Questions on whether this becomes the
    default landing route -- default to additive-only here unless product direction says
    otherwise.)
- Editing a tag from this page is explicitly **out of scope for this ticket** -- see DT-1113. This
  ticket is read/browse/search only; DT-1113 adds the correction affordance on top of it.

## **Acceptance criteria**

- `GET /library` returns both reviewed and unreviewed classified photos, is filterable by
  identity, species, reviewed status, and capture-date range, and paginates correctly (`total`
  reflects the full filtered result set, not just the current page's length).
- The Library page renders a browsable, filterable grid of classified photos, distinct from and
  reachable alongside the existing Review page.
- Every library result shows the same evidence a review item shows (photo, species,
  identity/confidence, capture date) plus whether/when it was reviewed.
- The existing `GET /review` queue endpoint and Review page are unchanged in behavior.

## **Testing requirements**

- `tests/test_review.py`: unit tests for `ReviewQueryService.library()` covering each filter
  independently and in combination, and pagination correctness (`total` vs. page length) with a
  fixture large enough to require more than one page.
- `tests/api/test_review.py` or a new `tests/api/test_library.py`: `GET /library` response shape
  and filter behavior at the API layer.
- Frontend: a build/lint pass (`npm run build`, `npm run lint`) plus a manual browser check of
  filtering and pagination, per this project's UI validation convention (no existing frontend test
  runner is set up for this codebase beyond build/lint).

## **Dependencies**

DT-1111 (photo capture date) should land first -- the library surface needs the same
`captured_at` plumbing/eager-load this ticket's `library()` method reuses, and building it twice
would duplicate work.

## **Suggested commit message**

`feat(DT-1112): add a searchable library of classified photos`
