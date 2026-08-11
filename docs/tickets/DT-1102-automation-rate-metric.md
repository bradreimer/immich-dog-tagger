# DT-1102: Reconcile review-queue definition and add a prominent automation-rate metric

## **ID**

DT-1102

## **Related spec**

[v1.1 Automation Coverage Dashboard](../specs/v1.1-automation-coverage-dashboard.md) -- FR-2, FR-3, FR-4

## **Priority**

Medium

## **Status**

Pending

## **Goal**

Make "review queue" mean the same thing everywhere it's used, add the missing rate field, and surface one prominent, explicitly-named automation metric via the API.

## **Context**

`MetricsService.learning_metrics()`'s `needs_review_count` (DT-1006) is derived as `eligible - unknown - confident`, which counts classifications with an identity set but confidence below threshold. Under the current single-threshold classify-time policy, the classifier never assigns an identity below its own threshold, so this count is effectively always 0 in practice -- it does not represent the actual manual work queue an operator sees on `/review` (which also includes candidate-conflict items and uses its own threshold parameter, potentially different from the classify-time one). Separately, there's no single prominent field answering "how much manual work is this system currently saving me," which is the headline number operators actually want -- everything else is supporting detail.

## **Acceptance criteria**

- `review_queue_size` (live, in `GET /metrics`) counts the same population `GET /review`'s default query would return: no review action yet, and (identity is unknown, or confidence is below the confident threshold, or there's a candidate conflict).
- `GET /metrics` exposes `unknown_rate` (unknown_count / eligible_count) alongside the existing `coverage` and `review_rate`.
- `GET /metrics` exposes a prominent, explicitly-named automation metric (e.g. `automation_rate` + `no_review_needed_count`), with the "does it include already-reviewed items or only current AUTO confident predictions" question (spec open question) resolved and documented in the field's description/docstring.
- The dedicated Metrics page (DT-1103) is updated to surface the new prominent metric and the corrected queue size (small, additive UI change -- not a redesign). Not Mission Control -- Learning Progress no longer lives there after DT-1103.
- All ratios remain `None` rather than `0`/misleading when `eligible_count == 0`, consistent with existing DT-1006 behavior.

## **Testing requirements**

- `MetricsService` tests asserting `review_queue_size` matches `ReviewQueryService.active_review()`'s result count for equivalent scenarios (shared fixture/scenario across both, so the two can't silently drift apart again).
- Tests for `unknown_rate` and the new automation metric, including the zero-eligible-items edge case.
- API test (`tests/api/test_metrics.py`) covering the new response fields.

## **Dependencies**

DT-1101 (shares the review-queue-size concept), DT-1006, DT-1103 (updates the Metrics page DT-1103 creates).

## **Suggested commit message**

`feat(DT-1102): reconcile review-queue metric and add automation-rate to /metrics`
