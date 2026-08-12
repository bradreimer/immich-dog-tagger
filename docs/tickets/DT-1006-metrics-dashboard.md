# DT-1006: Metrics and dashboard

## **ID**

DT-1006

## **Related spec**

[v1.0.0 Product & Engineering Specification](../specs/v1.0.0.md) -- FR-6, FR-7, section 6 (Metrics semantics)

## **Priority**

Medium

## **Status**

Completed

## **Goal**

Show users whether manual review is becoming less necessary.

## **Context**

v1.0.0's central product question is "is the review loop converging?" Before this ticket, `StatusService` exposed raw counts but no coverage/review-rate ratios, no classification-pass history, and no concept of a completed Reclassify pass to report progress against.

## **Implementation notes**

- Added `services/metrics.py::MetricsService.learning_metrics()`: persisted-query counts for `eligible_count`, `reviewed_count` (reused from `ReviewQueryService`), `labeled_example_count`, `confident_count`/`needs_review_count`/`unknown_count` (via the centralized `ClassifierPolicy` threshold, not a re-derived literal), `coverage`, `review_rate`, `last_reclassification`, and `pass_history` (oldest-first, for a trend).
- `coverage`/`review_rate` are `None` (not `0`) when `eligible_count == 0`, so the UI shows "—" instead of a misleading 0%.
- Denominators are explicit in both the API response field names and the UI copy under each stat ("X of Y eligible crops"), per the "make denominators explicit" requirement.
- No precision/accuracy metric is computed or shown -- v1.0.0 has no held-out evaluation set distinct from the reviews used as ground truth, so showing one would misrepresent confidence as validated accuracy.
- New `GET /metrics` route + `LearningMetricsResponse`/`ClassificationPassResponse` schemas.
- UI: "Learning Progress" card on Mission Control (coverage, review rate, labeled examples, last Reclassify status/timestamp/changed-count) plus a compact inline-SVG sparkline (`CoverageSparkline`) of confident coverage across the last 10 passes -- single series, so no legend needed, using the app's existing amber accent color rather than introducing a new palette.

## **Acceptance criteria**

- The main page gives a trustworthy snapshot of project learning progress that matches persisted database state.
- Every metric's denominator/scope is explicit.
- No precision/accuracy is shown without a valid held-out evaluation set.
- A compact trend of recent classification passes is visible.

## **Testing requirements**

`tests/test_metrics.py` (counts/ratios, empty project, pass history ordering + limit) and `tests/api/test_metrics.py`.

## **Dependencies**

DT-1001, DT-1004.

## **Suggested commit message**

`feat(DT-1002,DT-1006): add Reclassify action and learning-progress dashboard` (shipped in the same commit as DT-1002 -- the UI naturally couples the action with the progress it acts on)
