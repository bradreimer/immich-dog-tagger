# Species Timeline Chart Refinements: "Dogs Over Time" / "Cats Over Time"

Tracking issue: [#273](https://github.com/bradreimer/immich-dog-tagger/issues/273).

## Purpose

`docs/specs/species-volume-over-time-charts.md` (#271) shipped the "Dogs Over Time" and "Cats Over
Time" stacked-area charts on the Metrics tab (`SpeciesTimelineChart.tsx`), and explicitly deferred
in-chart identity filtering as future polish, not that iteration's scope. In real use, once a
library spans many years, the chart's X axis becomes illegible: `SpeciesTimelineChart` downsamples
to at most 20 points (`MAX_DISPLAY_POINTS`) and renders horizontal, non-rotated season labels at a
fixed 760px chart width, so long histories show overlapping, unreadable labels and skip seasons
entirely. This spec is a follow-on iteration making the existing chart usable at real-world data
volumes: legible rotated labels, every season actually rendered (no downsampling), a smoothed line,
click-to-isolate legend filtering, and a chart that fills the available card width instead of a
fixed pixel width.

## User story

As an owner reviewing "Dogs Over Time" / "Cats Over Time" on the Metrics tab over a library
spanning many years, I want a readable X axis, every season plotted, a smoother line, the ability
to isolate one pet's line by clicking its legend entry, and a chart that uses the full width of its
card, so the chart stays useful as my library's history grows instead of degrading into overlapping
labels and dropped data points.

## Goals

- Rotate the X-axis season labels (e.g. `"Winter 2025"`) to a vertical or steep angle so labels no
  longer overlap regardless of point count.
- Remove `SpeciesTimelineChart`'s downsampling: render one point per season for the entire range
  the backend already returns (the backend already zero-fills every season from a species'
  earliest to latest confirmed-photo season inclusive — see #271 — so this is a frontend-only
  change to stop discarding points client-side).
- Smooth the stacked-area band boundaries between points (curved interpolation) instead of the
  current straight-line (`M`/`L`) segments.
- Make each legend entry clickable: clicking one isolates that identity (chart redraws showing only
  that pet's band/line, scaled to its own max), clicking the same entry again (or a visible "show
  all" affordance) restores the full stacked view. Only one identity can be isolated at a time.
- Make the chart's rendered width track the card's actual available width (currently a fixed 760
  SVG viewBox width that does not stretch to fill a wider container), so the chart uses the full
  horizontal space of its card at any viewport width.

## Non-goals

- Any backend/API change. `MetricsService.species_timeline()`'s season bucketing, top-N/"Other"
  grouping, and zero-fill semantics are unchanged and already correct per #271 — this spec is
  frontend-only.
- Adopting a charting library. Stays hand-rolled inline SVG, consistent with #271's decision and
  this app's existing `ProgressOverTimeChart.tsx`/`DonutChart.tsx` house style.
- Multi-select legend filtering (isolating more than one identity at once), a legend "hide" toggle
  that doesn't isolate, or persisting the isolated-identity selection across page reloads. Single
  click-to-isolate / click-again-to-restore is the full scope here.
- Changing the season-bucketing grain (still one point per season, not month/quarter/week).
- Changing `ProgressOverTimeChart` or `DonutChart` — this is scoped to `SpeciesTimelineChart` only,
  even though `ProgressOverTimeChart` shares the same `MAX_DISPLAY_POINTS` downsampling pattern.
  Revisit that chart separately if it develops the same legibility problem.

## Requirements

### X-axis labels

- Render each season label rotated (e.g. `transform="rotate(-60 x y)"` or vertical) with
  `textAnchor="end"` (or equivalent) so labels read top-to-bottom/diagonally instead of overlapping
  horizontally, matching this app's existing SVG-text house style (no new dependency).
- Increase `PAD_BOTTOM` as needed to fit the rotated label height without clipping.

### Full season range, no downsampling

- Delete the `downsampleForDisplay`/`MAX_DISPLAY_POINTS` usage from `SpeciesTimelineChart`; plot
  every point in the `points` prop as received from the API.
- The chart's horizontal-space fix (below) is what keeps this legible at high point counts, rather
  than dropping data.

### Smoothed line

- Replace the straight-segment `areaPath()` top/bottom boundary construction with a smoothed curve
  (e.g. Catmull-Rom-to-Bezier conversion, implemented inline with no new dependency, consistent with
  the Non-goals above) through the same point coordinates.
- The stacked semantics (each band's bottom = previous band's top, bands never overlap, total
  height at any X position still sums to the true stacked total) are preserved — only the rendered
  curve between points changes, not the data or stacking math.

### Legend click-to-filter

- Each legend `<li>` becomes a `<button>` (keyboard-accessible, with a visible focus/selected
  state) that toggles an "isolated identity" selection local to that chart instance.
- When an identity is isolated: render only that identity's band (or a single line/area if a single
  band is visually indistinguishable from a stack), the tooltip shows only that identity's count,
  and the Y-axis scales to that identity's own max rather than the full stacked total.
- Clicking the isolated legend entry again (or a distinct "Show all" control) clears the isolation
  and returns to the full stacked view.
- Isolating one chart's legend does not affect the other chart ("Dogs Over Time" and "Cats Over
  Time" isolate independently).

### Full-width chart

- Measure the chart's actual rendered container width (e.g. via `ResizeObserver` on a wrapper
  `div`, no new dependency) and size the SVG's `viewBox`/rendered width to match it, keeping
  `HEIGHT` fixed, instead of the current fixed `WIDTH = 760` that leaves unused horizontal space (or
  clips) on wider/narrower cards.
- Behavior at very narrow widths (e.g. mobile) degrades gracefully — labels may still rotate/overlap
  at extreme widths, but the chart never overflows its card or breaks layout.

## Acceptance criteria

- Given a species timeline spanning more than 20 seasons, every season in the API response renders
  as its own point on the chart (verified by point count in the rendered SVG, not just the
  underlying data).
- Given that same long history, X-axis season labels do not visually overlap at the chart's default
  rendered width.
- Given the stacked area bands, the boundary between any two adjacent points is a curve, not a
  straight line, while the total stacked height at each plotted X position still equals the sum of
  that season's per-identity counts (smoothing changes the drawn curve between points, not the
  values at the points).
- Given a user clicks a legend entry, the chart re-renders showing only that identity; clicking it
  again restores the full stacked view with all identities.
- Given the browser window (or the card) is resized wider or narrower, the chart's rendered width
  visibly follows, filling the card's available width rather than staying a fixed pixel width.
- `SpeciesTimelineChart`'s existing accessibility (`role="img"` + `aria-label`) and hover tooltip
  behavior continue to work in both the full-stack and isolated-identity views.

## Open questions

- Exact rotation angle (45° vs. 60° vs. fully vertical 90°) and whether every label renders or
  every-other label at very high point counts once labels are legible — left to implementation to
  tune against the increased `PAD_BOTTOM`; the acceptance bar is "no visual overlap," not a specific
  angle.
- Whether isolating a legend identity should also dim (rather than fully hide) the "Other" band as
  context — left to implementation; either satisfies "isolates that identity" as long as the
  isolated identity's own data is what the Y axis scales to and the tooltip reflects.
