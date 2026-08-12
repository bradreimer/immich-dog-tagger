# DT-1101: Snapshot labeled-example count and review-queue size on each classification pass

## **ID**

DT-1101

## **Related spec**

[v1.1 Automation Coverage Dashboard](../specs/v1.1-automation-coverage-dashboard.md) -- FR-1

## **Priority**

Medium

## **Status**

Completed

## **Goal**

Make the full trend story (review queue shrinking, labeled examples growing) queryable across classification passes via the REST API, not just the confident/needs-review/unknown/changed counts DT-1006 already captures.

## **Context**

`GET /metrics`'s `pass_history` (DT-1006) records `confident_count`/`needs_review_count`/`unknown_count`/`changed_count` per pass, but not the labeled-example count or review-queue size at that point in time. Both are only queryable as live, present-tense values today, so a client can't plot "labeled examples grew from 40 to 65 over these 4 passes" or "the queue shrank from 820 to 175" -- exactly the trend story that makes the dashboard meaningful, per the operator feedback this ticket is based on.

## **Implementation notes**

- Added nullable `labeled_example_count`/`review_queue_size` columns to `ClassificationPass` (additive migration: `_ensure_classification_pass_trend_columns` in `database.py`, following the existing `_ensure_classification_pass_columns` pattern).
- Added `ReviewQueryService.review_queue_count()`: an efficient `COUNT` query matching exactly what `active_review()`'s default filter would return (no review action yet, and unknown or below the confident threshold) -- reused live by DT-1102 and per-pass by this ticket, so the two definitions can never drift apart (proven by a shared-scenario test).
- `ReclassifyService._snapshot_trend_fields()` records both fields right before a pass finishes -- on full success and on both early-exit paths (zero labeled examples, zero eligible crops). Deliberately **not** called on a mid-run failure: a partial pass has no well-defined final snapshot, so those fields stay `null` on a `FAILED` pass (matches the "not backfilled" additive-only design).
- `ReclassifyResult`, the `_reclassify_handler` job-result dict, `ClassificationPassSummary`, and `ClassificationPassResponse` all carry the two new fields through to the API response.

## **Acceptance criteria**

- `ClassificationPass` persists `labeled_example_count` and `review_queue_size` as of when the pass completed.
- `GET /metrics`'s `pass_history` entries include both new fields for every pass created after this ships.
- Existing passes (created before this ships) are unaffected -- the new columns are nullable/additive, not backfilled (backfill isn't reliably reconstructable; see the spec's resolved open questions).
- `ReclassifyService` populates both fields as part of the same commit that finalizes a pass, so they can never be missing on a `COMPLETED` pass.

## **Testing requirements**

- `ReclassifyService` unit tests asserting `labeled_example_count`/`review_queue_size` are recorded correctly on a completed pass, on both early-exit paths, and remain `null` on a failed pass.
- `MetricsService`/API tests asserting `pass_history` serializes the new fields.
- A migration test (matching the existing `_ensure_classification_pass_columns` pattern in `tests/test_database.py`) confirming existing databases upgrade cleanly with the new nullable columns.
- A shared-scenario test proving `review_queue_count()` and `active_review()` agree on the same population (`tests/test_review.py`).

## **Dependencies**

DT-1001, DT-1006 (this extends both).

## **Suggested commit message**

`feat(DT-1101): snapshot labeled-example count and review-queue size per pass`
