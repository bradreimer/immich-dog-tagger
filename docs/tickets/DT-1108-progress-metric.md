# DT-1108: Progress Over Time chart -- dual-axis trend with reduction callout

## **ID**

DT-1108

## **Related spec**

[v1.2 Visual Style Refresh](../specs/v1.2-visual-style-refresh.md) -- amends the "no dual-axis
charts" non-goal for this one chart, on explicit request with a reference design.

## **Priority**

Medium

## **Status**

Completed

## **Goal**

Replace the Metrics page's two split trend charts (a 3-series "Progress Over Time" chart and a
separate single-series "Labeled Examples" chart, from DT-1105) with one consolidated chart that
makes the core outcome immediately legible:

> As the user reviews more images and adds labeled examples, the amount of manual review required
> should decrease.

This is a progress/workload visualization, not a model-accuracy chart -- consistent with every
prior metrics ticket (DT-1006, DT-1101, DT-1102), it must not claim statistical accuracy without a
held-out evaluation set.

## **Context**

The user supplied a detailed spec (informal, pre-template) and a reference image: a dual-axis line
chart (left axis "Images/Crops" for Needs Review/Confidently Classified/Unknown, right axis
"Labeled Examples" in a matching purple) with direct value labels on every point, a per-pass hover
tooltip, a legend, and a footer strip of five stat tiles including a "Review Queue Reduction"
percentage since the first recorded pass.

This directly revisits a decision DT-1105 made deliberately: the `dataviz` skill treats a dual
y-axis as the single most common charting mistake, so DT-1105 split "Progress Over Time" (queue/
confident/unknown, one shared axis) from "Labeled Examples" (its own chart) rather than combine
them. The user has now asked for the combined version twice, with a reference design that
*mitigates* the usual dual-axis ambiguity rather than ignoring it: the right axis's title and tick
labels are colored to match the Labeled Examples line, and every point carries a direct numeric
label, so a reader is never left guessing which axis a given point reads against. Given that
mitigation and an explicit, repeated request, this ticket implements the dual-axis version and
amends the v1.2 non-goal accordingly (see that spec's Non-goals section).

Three things from the user's spec don't map cleanly onto this codebase as written, resolved here:

- **"Needs Review" data source.** The user's spec describes "items classified below the confident
  threshold but with a plausible candidate," which matches `ClassificationPass.needs_review_count`
  by name -- but DT-1102 already established that field is effectively always 0 under the current
  single-threshold policy, and introduced `review_queue_size` as the field that actually reflects
  what a human needs to look at. Plotting the always-zero field would silently produce a flat line
  at 0 and contradict every other "review queue" number on this same page. This chart plots
  `review_queue_size` under the "Needs Review" label, matching what DT-1102 already did for the
  live metric.
- **No true "Initial / After Pipeline" data point exists.** `ClassificationPass` rows are only
  ever created by `ReclassifyService` (confirmed by inspection: `classification.py`'s initial
  `full_pipeline`/`classify` path never touches `ClassificationPass`). So the *first* entry in
  `pass_history` is already the result of the first Reclassify run, not a snapshot of the raw
  state right after the initial pipeline pass -- that raw state is never persisted as a pass. Per
  the project's "don't reconstruct historical values that would change the meaning of historical
  passes" rule (which the user's own spec also states), this chart doesn't fabricate an "Initial"
  point. Passes are labeled "Pass #<id>" (matching the existing sparkline/trend-chart convention
  elsewhere on this page) and the reduction callout says "since pass #<first recorded id>" rather
  than "since initial pass."
- **`review_reduction` formula, as specified**: `1 - current_review_queue_size /
  first_recorded_review_queue_size`, computed from the earliest and latest `pass_history` entries
  that have a non-null `review_queue_size` (older passes predating DT-1101 have `null` there and
  are excluded, per that ticket's "not backfilled" design). Omitted (not shown as 0% or a
  divide-by-zero) when the first recorded value is 0.

No backend or API changes are needed: every field this chart uses (`eligible_count`,
`confident_count`, `unknown_count`, `review_queue_size`, `labeled_example_count`, pass `id`,
`completed_at`) is already returned by `GET /metrics`'s `pass_history` (DT-1006/DT-1101). The
"query aggregated pass-level metrics, not individual images" and "limit historical points
returned" performance requirements from the user's spec are already satisfied by the existing
`MetricsService` (COUNT-based queries, `history_limit=10`). The "don't treat a running
reclassification as a completed historical pass" requirement is already satisfied structurally --
`_snapshot_trend_fields()` only runs on a pass's success/early-exit path, never mid-run (DT-1101).

## **Implementation notes**

- New `ui/src/features/metrics/components/ProgressOverTimeChart.tsx`: dual-axis SVG line chart
  (hand-rolled, matching the project's existing chart pattern -- no new charting dependency).
  Left axis: eligible-crop counts (Needs Review/Confidently Classified/Unknown, one shared scale
  since all three are "count of eligible crops"). Right axis: Labeled Examples, its own scale,
  axis title and ticks colored to match the dashed purple line. Direct value labels on every
  point. Hover shows a hairline crosshair and a tooltip with the pass's full breakdown, eligible
  count, and that specific pass's reduction-since-first-recorded value.
- Removed the old two-chart split and `TrendChart.tsx` (now unused -- confirmed no other
  references before deleting).
- Removed the automation-rate trend delta added in DT-1106 from the Automation banner. It and the
  new "Review Queue Reduction" tile measure related but differently-normalized things (percentage-
  point change in automation rate vs. percentage reduction in raw queue count) and showing two
  differently-worded "improved since earlier" numbers on the same page was more confusing than
  either alone. The new, more precisely specified metric is now the page's single canonical trend
  indicator.
- `MetricsPage.tsx` now has three explicit states for this section, per the user's spec:
  - **No recorded passes**: an explanatory empty-state card ("Run the pipeline and review your
    first batch of images. Your progress will appear here after your first Reclassify pass.").
  - **Exactly one pass with recorded queue/example data**: current counts as stat tiles, no line
    chart (a single point isn't a trend), with a note that trends appear after the next pass.
  - **Two or more**: the full chart, tooltip, legend, and the five-tile footer (Labeled Examples,
    Confidently Classified, Needs Review, Unknown, Review Queue Reduction), using the latest
    pass's counts and the chart's own series colors for each tile's icon, so the footer visually
    reads as part of the chart rather than a separate widget.
  - The "Labeled Examples" footer tile's "Across N dogs" subtext uses a live active-dog count
    (`GET /dogs`), not a fabricated number.

## **Acceptance criteria**

- Metrics displays one "Progress Over Time" chart (not two separate charts).
- Needs Review, Confidently Classified, and Unknown are plotted on a shared left axis; Labeled
  Examples on its own right axis, visually tied to its line via matching color.
- Every plotted point has a direct value label; the chart is readable without hovering.
- Hovering a pass shows its full breakdown plus eligible-item count.
- A "Review Queue Reduction" percentage is shown when >= 2 qualifying passes exist, omitted (not
  a fabricated 0%) when the earliest recorded queue size is 0.
- Zero-pass, single-pass, and multi-pass states each render something sensible -- never a broken
  or blank chart.
- No label claims accuracy, probability, or treats a reviewed label as classifier performance.
- `npm run build` and `npm run lint` pass.
- No backend, database, or API changes.

## **Testing requirements**

- Manual visual verification of all three states (empty/single/multi-pass), light and dark, in an
  isolated scratch environment, including hover-tooltip content.
- This UI change has no frontend automated test suite to extend (none exists in this repo today);
  the underlying data it consumes (`pass_history`, `review_queue_size`, nullability) is already
  covered by the existing `tests/test_metrics.py` / `tests/test_reclassify.py` /
  `tests/api/test_metrics.py` suites, which are unaffected since no backend code changed.

## **Dependencies**

DT-1101, DT-1102, DT-1105 (this replaces DT-1105's two-chart Metrics trend section).

## **Suggested commit message**

`feat(DT-1108): consolidate Metrics trend into one dual-axis Progress Over Time chart`
