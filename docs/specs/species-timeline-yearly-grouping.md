# Species Timeline Chart: Yearly Grouping

Tracking issue: [#275](https://github.com/bradreimer/immich-dog-tagger/issues/275).

## Purpose

Even after #273's legibility fixes (rotated labels, no downsampling, smoothed curve, full-width
sizing), "Dogs Over Time" / "Cats Over Time" still plot one point per *season* -- four points per
year. Over a library spanning many years that is still visually dense: more points than the chart
needs to convey the trend the chart exists to show. This spec reduces the granularity to one point
per *calendar year*, superseding #271's original season-grain decision and #273's "changing the
season-bucketing grain" Non-goal. #271's spec explicitly left this door open ("Revisit only if
seasonal buckets prove too coarse or too fine in practice") -- this is that revisit, in the
too-fine direction.

## User story

As an owner reviewing "Dogs Over Time" / "Cats Over Time" on the Metrics tab, I want confirmed
photo counts grouped by calendar year instead of by season, so the chart reads as a clear
multi-year trend instead of a dense quarterly sawtooth.

## Goals

- Change `MetricsService.species_timeline()`'s bucketing key from `(year, season)` to plain
  `captured_at.year` -- one point per calendar year instead of four.
- `SpeciesTimelinePoint.label` becomes the year as a string (e.g. `"2025"`) instead of
  `"{Season} {Year}"`.
- Zero-fill gap years between a species' earliest and latest confirmed-photo year, same semantics
  #271 established at season grain, just at year grain (no in-between year with zero confirmed
  photos across every pet of that species is skipped -- it isn't rendered at all, same as before).
- `SpeciesTimelineChart`'s X-axis labels render horizontally again: #273 rotated them vertically to
  stay legible at up to 4x as many points; at one point per year that's no longer necessary and
  horizontal, centered year labels are the more idiomatic and readable default.
- Per-species scoping, the null-`captured_at` exclusion, legend click-to-isolate, curve smoothing,
  and full-width sizing (all from #271/#273) are unchanged in behavior -- they now just operate on
  fewer, yearly points.
- Raise `TOP_N_TIMELINE_IDENTITIES` from 4 to 6, so up to 6 pets each get their own band before the
  rest fold into "Other" (raised in review alongside the grain change, at the same time the palette
  below is extended to support it).
- Extend this app's categorical chart palette with two more validated colors (dataviz skill slots
  5 "magenta" and 6 "green", added as new `--chart-6`/`--chart-7` CSS variables) so 6 individually
  colored bands + "Other" have 7 visually distinct colors, ordered
  blue/aqua/violet/yellow/magenta/green/red -- the ordering validated with
  `scripts/validate_palette.js` for this exact 7-hue set (not the original 5-color set's slot-number
  order, which would put a warm color and yellow adjacent and fail validation).

## Non-goals

- A user-configurable granularity toggle (season vs. year, or any other grain). This replaces the
  season grain outright; it isn't an added option alongside it.
- Any change to `_species_breakdown()`, `_detection_coverage()`, or `ProgressOverTimeChart`.
- Sub-year bucketing of any kind (month/quarter/week). Year is the new fixed grain -- same
  "fixed for this iteration, revisit if it proves wrong" stance #271 took for season.
- Raising `TOP_N_TIMELINE_IDENTITIES` past 6, or a further palette extension past 7 slots. The
  dataviz skill's documented 8-hue set has one slot (orange) left unused here deliberately -- it
  sits adjacent to yellow (already chart-4) in the validated default order and using it would need
  re-validating a different ordering.

## Requirements

### Year bucketing

- Bucket key is `captured_at.year` (a plain `int`). The Winter-spans-a-year-boundary special
  case from season bucketing no longer applies -- a calendar year doesn't cross itself, so there's
  no equivalent merge/rollover logic to carry forward. `_season_bucket`/`_next_season_bucket`/
  `_season_sort_key`/`_SEASON_BY_MONTH`/`_SEASON_SEQUENCE` are removed as dead code once nothing
  references them.
- Continuous from a species' earliest to latest confirmed-photo year inclusive, zero-filled for
  any in-between year with no confirmed photos for that species at all (unchanged rule, year
  grain).
- Label is `str(year)`, e.g. `"2025"`.

### Frontend

- `SpeciesTimelineChart` renders X-axis labels horizontally (`textAnchor="middle"`, no rotation),
  reverting #273's vertical rotation and its enlarged `PAD_BOTTOM` (no longer needed at this point
  density).
- `MetricsPage.tsx` card descriptions read "Confirmed dog/cat photos per year, by pet." (was "per
  season").
- The chart's `aria-label` says "per year"/"year(s)" instead of "per season"/"season(s)".

### Palette extension and top-N

- `index.css` adds `--chart-6` (magenta, `#e87ba4` light / `#d55181` dark) and `--chart-7` (green,
  `#008300`, mode-invariant) alongside the existing `--chart-1..5`, in both the light `:root` block
  and the `.dark` block, plus their `@theme inline` `--color-chart-6/7` mappings -- `--chart-1..5`
  are untouched (still blue/aqua/violet/yellow/red) since `ProgressOverTimeChart` also depends on
  `--chart-3`.
- `SpeciesTimelineChart`'s `BAND_COLORS` array reorders to
  `[chart-1, chart-2, chart-3, chart-4, chart-6, chart-7, chart-5]` (blue, aqua, violet, yellow,
  magenta, green, red) -- the validated order for this 7-hue set, not CSS-variable-number order.
- `MetricsService.TOP_N_TIMELINE_IDENTITIES` becomes `6`.

## Acceptance criteria

- Given confirmed dog photos in Dec 2025 and Jan 2026 for the same dog, "Dogs Over Time" now
  buckets them into two separate points, `"2025"` and `"2026"` -- the Winter cross-year merge from
  #271 was a season-only concept and no longer applies.
- Given a dog with confirmed photos only in 2023 and 2026, and another dog of the same species with
  data spanning that whole range, 2024 and 2025 render as zero-filled points; a year with literally
  no confirmed photos across every pet of that species isn't rendered at all.
- Given more than 6 dogs with confirmed photos, the top-6 + "Other" stacking assigns each of the 6
  its own band (7 total with "Other"), each a distinct color from the extended palette.
- X-axis labels render horizontally, legibly, for a multi-decade history.
- Legend click-to-isolate, the smoothed curve, and full-width sizing continue to work unchanged.
- The 7-color palette (in the order specified above) passes `scripts/validate_palette.js` in both
  light and dark mode with no hard FAIL (a WARN-band CVD pair is acceptable given this chart's
  existing legend + tooltip secondary encoding).

## Open questions

None -- this is a straightforward grain change; the "revisit if it proves wrong" escape hatch
#271 established stays available for any future iteration.
