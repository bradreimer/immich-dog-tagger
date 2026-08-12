# DT-1102: Reconcile review-queue definition and add a prominent automation-rate metric

## **ID**

DT-1102

## **Related spec**

[v1.1 Automation Coverage Dashboard](../specs/v1.1-automation-coverage-dashboard.md) -- FR-2, FR-3, FR-4

## **Priority**

Medium

## **Status**

Completed

## **Goal**

Make "review queue" mean the same thing everywhere it's used, add the missing rate field, and surface one prominent, explicitly-named automation metric via the API.

## **Context**

`MetricsService.learning_metrics()`'s `needs_review_count` (DT-1006) is derived as `eligible - unknown - confident`, which counts classifications with an identity set but confidence below threshold. Under the current single-threshold classify-time policy, the classifier never assigns an identity below its own threshold, so this count is effectively always 0 in practice -- it does not represent the actual manual work queue an operator sees on `/review`. Separately, there's no single prominent field answering "how much manual work is this system currently saving me," which is the headline number operators actually want -- everything else is supporting detail.

## **Implementation notes**

- Added `review_queue_size`, `unknown_rate`, `no_review_needed_count`, and `automation_rate` to `LearningMetrics`/`LearningMetricsResponse`. `needs_review_count` was kept as-is (existing, tested field, part of the confident/needs-review/unknown exhaustive partition) rather than redefined, since removing it would be a breaking API change for an already-shipped v1.0.0 field -- `review_queue_size` is the new, operationally meaningful number.
- `review_queue_size` = `ReviewQueryService.review_queue_count()` (added in DT-1101): no review action yet, and identity is unknown or confidence is below the confident threshold.
- Investigated the spec's "or there's a candidate conflict" clause during implementation: it turned out to already be redundant, not a third condition to add. `_review_reason()` only ever assigns `"candidate-conflict"` to rows that are *already* selected by "identity unknown or confidence below threshold" (it's checked after the unknown case, on rows guaranteed to have confidence below threshold) -- a confidently-classified item with multiple candidates is never in the queue today. So the two-condition query already matches `/review`'s actual behavior exactly; no candidate-specific clause was needed. Verified with a shared-scenario test rather than assumed.
- `no_review_needed_count = eligible_count - review_queue_size` and `automation_rate = no_review_needed_count / eligible_count` (or `None` if `eligible_count == 0`). Resolved the spec's open question explicitly: this **includes** already-reviewed items, not just confident AUTO predictions -- an already-reviewed item needs no further review regardless of its confidence, so excluding it would understate how much manual work is actually done. Documented inline in `metrics.py`.
- `unknown_rate = unknown_count / eligible_count` (or `None` if zero), following the same explicit-denominator pattern as `coverage`/`review_rate`.
- Metrics page (DT-1103) updated: a new prominent "Automation" banner card ("X% -- N of M images require no manual review right now") above the existing Learning Progress card, a new "Review queue" stat tile (replacing the buried `needs_review_count` sub-line), and `unknown_rate` shown alongside the unknown count.

## **Acceptance criteria**

- `review_queue_size` (live, in `GET /metrics`) counts the same population `GET /review`'s default query would return.
- `GET /metrics` exposes `unknown_rate` alongside the existing `coverage` and `review_rate`.
- `GET /metrics` exposes a prominent, explicitly-named automation metric (`automation_rate` + `no_review_needed_count`), with the "does it include already-reviewed items" question resolved and documented.
- The dedicated Metrics page (DT-1103) is updated to surface the new prominent metric and the corrected queue size.
- All ratios remain `None` rather than `0`/misleading when `eligible_count == 0`.

## **Testing requirements**

- `MetricsService` tests asserting `review_queue_size`/`unknown_rate`/`no_review_needed_count`/`automation_rate` on a mixed scenario (confident, reviewed, and pending items) and on the zero-eligible-items edge case.
- A shared-scenario test proving `ReviewQueryService.review_queue_count()` matches `active_review()`'s result count exactly (`tests/test_review.py`), so the two can't silently drift apart.
- API test (`tests/api/test_metrics.py`) covering the new response fields.
- Manual visual verification of the updated Metrics page against an isolated scratch backend.

## **Dependencies**

DT-1101 (shares the review-queue-size concept), DT-1006, DT-1103 (updates the Metrics page DT-1103 creates).

## **Suggested commit message**

`feat(DT-1102): reconcile review-queue metric and add automation-rate to /metrics`
