# TICKET 06: Metrics and dashboard

## Status
Completed

## Implementation notes
- Added `services/metrics.py::MetricsService.learning_metrics()`: persisted-query counts for `eligible_count`, `reviewed_count` (reused from `ReviewQueryService`), `labeled_example_count`, `confident_count`/`needs_review_count`/`unknown_count` (via the centralized `ClassifierPolicy` threshold, not a re-derived literal), `coverage`, `review_rate`, `last_reclassification`, and `pass_history` (oldest-first, for a trend).
- `coverage`/`review_rate` are `None` (not `0`) when `eligible_count == 0`, so the UI shows "—" instead of a misleading 0%.
- Denominators are explicit in both the API response field names and the UI copy under each stat ("X of Y eligible crops"), per the "make denominators explicit" requirement.
- No precision/accuracy metric is computed or shown -- v1.0.0 has no held-out evaluation set distinct from the reviews used as ground truth, so showing one would misrepresent confidence as validated accuracy.
- New `GET /metrics` route + `LearningMetricsResponse`/`ClassificationPassResponse` schemas.
- UI: "Learning Progress" card on Mission Control (coverage, review rate, labeled examples, last Reclassify status/timestamp/changed-count) plus a compact inline-SVG sparkline (`CoverageSparkline`) of confident coverage across the last 10 passes -- single series, so no legend needed, using the app's existing amber accent color rather than introducing a new palette.
- Tests: `tests/test_metrics.py` (counts/ratios, empty project, pass history ordering + limit) and `tests/api/test_metrics.py`.

## Goal
Show users whether manual review is becoming less necessary.

## Steps
1. Define persisted queries for eligible, reviewed, labeled-example, confident, review, and unknown counts.
2. Add recommendation coverage and review rate.
3. Add last reclassification and pass history.
4. Track prediction changes between passes.
5. Add a compact trend graph over passes/batches.
6. Make denominators explicit in labels/tooltips.
7. Do not show precision/accuracy unless a valid held-out evaluation set exists.

## Done when
The main page gives a trustworthy snapshot of project learning progress and the values match database state.
