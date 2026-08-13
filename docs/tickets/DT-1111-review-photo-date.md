# DT-1111: Show photo capture date prominently during review

## **ID**

DT-1111

## **Related spec**

[v1.4-trustworthy-photo-library.md](../specs/v1.4-trustworthy-photo-library.md) (FR-1)

## **Priority**

High

## **Status**

Completed

## **Goal**

Show each photo's capture date next to its predicted identity and confidence everywhere a
classification is shown, starting with the Review page. The date is a key piece of evidence users
already rely on to distinguish visually similar dogs across different years -- today it isn't
shown anywhere in the review UI at all.

## **Context**

The data already exists and requires no new ingestion: `Asset.captured_at`
(`src/immich_dog_tagger/models.py:169`) is populated from Immich's `fileCreatedAt` field by
`scanner.py:56` (`captured_at=immich_asset.captured_at`) for every asset today. The gap is
entirely in plumbing this existing field through to the review response and UI:

- `ReviewItem` (`src/immich_dog_tagger/services/review_query.py:50-58`) has no `captured_at`
  field. The only `captured_at` currently exposed anywhere in the review response is
  `ReviewSuggestion.captured_at` (line 47) -- the capture date of the *matched reference example*,
  not the date of the photo currently being reviewed. These are different photos and must not be
  confused.
- `_to_review_item()` (line 308) builds a `ReviewItem` from `classification.crop`, but never
  touches `classification.crop.detection.asset` for anything other than species (which is a
  `Crop`-level column, not an `Asset` one -- see DT-1110). Reaching the asset requires
  `classification.crop.detection.asset.captured_at`.
- `_REVIEW_ITEM_RELATIONSHIPS` (review_query.py:21-26) eager-loads `Crop.detection` but not
  `Detection.asset`. Without adding that hop to the eager-load chain, touching
  `.asset.captured_at` for every item in a review-queue page would issue one extra query per row
  (the exact N+1 shape DT-1008 already found and fixed elsewhere in this file).
- `ReviewItemResponse` (`src/immich_dog_tagger/api/schemas.py`) and its `from_item` constructor
  have no `captured_at` field to serialize the new `ReviewItem` field.
- The frontend `ReviewItem` type (`ui/src/types/review.ts`) and `ReviewCard`/`PredictionCard`
  components have nowhere to render it.

## **Implementation notes**

- `review_query.py`: extend `_REVIEW_ITEM_RELATIONSHIPS`'s first entry to
  `selectinload(CropClassification.crop).selectinload(Crop.detection).selectinload(Detection.asset)`
  (new `Detection` import already exists in this file's context via `Crop`; add `Detection` and
  `Asset` imports as needed). Add `captured_at: datetime | None` to the `ReviewItem` dataclass.
  Populate it in `_to_review_item()` from `classification.crop.detection.asset.captured_at`,
  guarding for a null `detection`/`asset` the same defensive way `correction.py:63-67` already
  does (test fixtures and, in principle, orphaned rows can lack these).
- `api/schemas.py`: add `captured_at: datetime | None` to `ReviewItemResponse`; set it in
  `from_item`.
- `ui/src/types/review.ts`: add `captured_at: string | null` to `ReviewItem`.
- Frontend display: show the formatted date (e.g. "March 3, 2019") near the prediction/confidence
  in `PredictionCard.tsx` or directly on `ReviewCard.tsx`, with an explicit "Date unknown" state
  when `captured_at` is null -- never a blank field or a fallback to some other timestamp (e.g.
  `CropClassification.created_at`, which is when Dog Tagger processed the photo, not when it was
  taken, and would be actively misleading here).
- `review_export.py` already prints `item.suggestion.captured_at` (the matched example's date,
  line 96-97) -- add the review item's own `captured_at` alongside it, clearly labeled to avoid
  the two dates being confused in the export text.

## **Acceptance criteria**

- `GET /review` and `GET /review?...` responses include each item's own photo capture date.
- The Review page shows the photo's capture date near the predicted identity/confidence, with an
  explicit "date unknown" state when the underlying asset has no capture date.
- No N+1 query regression: fetching a review page of N items issues a constant number of queries
  regardless of N (verified the same way DT-1008's fixes were verified).
- The review export text file shows the reviewed photo's own capture date, distinguishable from
  the matched example's capture date it already prints.

## **Testing requirements**

- `tests/test_review.py`: extend (or add) a test asserting `ReviewItem.captured_at` reflects
  `Asset.captured_at` through the full `Crop -> Detection -> Asset` chain, and is `None` when the
  asset has no capture date.
- `tests/api/test_review.py`: assert `GET /review` response items include `captured_at`.
- A query-count assertion (matching the pattern used for DT-1008's N+1 fixes) confirming the new
  eager-load hop doesn't reintroduce a per-row query.
- `tests/test_review_export.py`: assert the exported text includes the review item's own capture
  date.

## **Dependencies**

None. This is the smallest, most foundational piece of the v1.4 spec -- DT-1112 (library) reuses
this same field once it exists, so landing this first avoids duplicating the eager-load/plumbing
work.

## **Suggested commit message**

`feat(DT-1111): show photo capture date during review`
