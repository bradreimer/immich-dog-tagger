# Species Volume Over Time: "Dogs Over Time" / "Cats Over Time" Charts

Tracking issue: [#271](https://github.com/bradreimer/immich-dog-tagger/issues/271).

## Purpose

The Metrics tab's "Progress Over Time" chart (`ProgressOverTimeChart.tsx`,
[docs/specs/v1.1-automation-coverage-dashboard.md](v1.1-automation-coverage-dashboard.md)) plots
review-queue/labeled-example counts per *reclassification pass* — its X axis is `Pass #{id}`, not
calendar time, because it exists to show classifier learning progress across pipeline runs, not
photo-taking activity over the calendar. That spec's Non-goals explicitly deferred "new UI chart
types beyond what's needed to plot the additional trend fields this spec adds" to whichever ticket
needed them next.

Nothing on the Metrics tab today answers "how many photos of each pet did we take, and when" — the
closest existing concept is `MetricsService._species_breakdown()`, a point-in-time snapshot (current
totals per species), and the Insights page's per-identity `PetOccurrence` facts
([docs/specs/v1.6-pet-insights.md](v1.6-pet-insights.md)), which are scoped to one identity at a
time, not a library-wide trend. This spec adds two new charts to the Metrics tab, below "Progress
Over Time," answering that question at the library level: confirmed photo volume over calendar
time, split by species and broken down by individual pet.

## User story

As an owner reviewing the Metrics tab, I want to see how many confirmed dog photos and cat photos
were taken each season, broken down by which pet, so I can see seasonal patterns (e.g. more outdoor
photos in summer) and which pets make up my library's volume over time — not just the current
point-in-time totals `_species_breakdown()` already shows.

## Goals

- Add two new cards to the Metrics tab, directly below the existing "Progress Over Time" card:
  "Dogs Over Time" and "Cats Over Time."
- Each is a stacked area chart. X axis: calendar time, bucketed by season, labeled `"{Season}
  {Year}"` (e.g. `"Fall 2026"`). Y axis: count of confirmed photos in that season, stacked by
  individual pet identity (top N by total volume across the whole displayed range, remaining
  identities grouped into a single "Other" band) — the two charts are the per-species split of the
  same underlying concept, not one combined dog+cat chart (resolved in review; see Open questions
  for the rejected alternative).
- Source the counts from `PetOccurrence` joined to `Asset.captured_at`, consistent with how
  `docs/specs/v1.6-pet-insights.md`/`v1.7-pluginable-insights.md`'s per-identity time-based facts
  (`MostActiveMonthProvider`, etc.) already read "when was this photo taken" — not `Asset.created_at`
  (pipeline ingestion time), which answers a different question (throughput, already covered by
  `_detection_coverage()`).
- Seasons with zero confirmed photos between an identity's first and last appearance still render
  as a zero-height point, so a gap in the timeline reads as "no photos that season," not a break in
  the chart.
- New read-only backend surface(s) computing this at read time, matching ADR-004's existing
  "never store a derived conclusion" policy — no new schema, no materialized/precomputed table.

## Non-goals

- A combined dog+cat single chart (one stacked area with two bands, "dog" and "cat"). Considered
  and rejected in review in favor of two separate per-species charts, each stacked by individual
  pet identity — see Open questions.
- Changing `_species_breakdown()`, `_detection_coverage()`, or `ProgressOverTimeChart`'s existing
  per-pass X axis. Those stay exactly as they are; this is purely additive.
- A custom date-range picker or user-adjustable bucket size (season is fixed for this iteration).
  Revisit only if seasonal buckets prove too coarse or too fine in practice.
- A general-purpose charting library adoption. Every existing Metrics chart
  (`ProgressOverTimeChart.tsx`, `DonutChart.tsx`) is hand-rolled inline SVG with no charting
  dependency; the new stacked-area component follows the same house style unless the implementer
  finds a concrete reason a dependency is warranted (left to implementation).
- Southern-Hemisphere season labeling, or a per-deployment hemisphere setting. Seasons are the
  standard Northern-Hemisphere meteorological definition (see Requirements) — this is a
  single-operator, local-first tool per `CONTRIBUTING.md`, and revisiting this is cheap later if a
  real need appears.
- Filtering the charts by identity, date range, or species-within-a-chart — each chart already is
  the species filter; further slicing is future polish, not this iteration.

## Requirements

### Season bucketing

Standard Northern-Hemisphere meteorological seasons, by calendar month of `Asset.captured_at`:

| Season | Months |
| --- | --- |
| Winter | Dec, Jan, Feb |
| Spring | Mar, Apr, May |
| Summer | Jun, Jul, Aug |
| Fall | Sep, Oct, Nov |

Winter spans a year boundary; it is labeled by **the December's calendar year** (e.g. Dec 2025 +
Jan 2026 + Feb 2026 all bucket into `"Winter 2025"`). This matches the common "meteorological
winter is named for the year it starts" convention and keeps the rule a pure function of
`captured_at` (month, and year-or-year-minus-1 for Jan/Feb) with no cross-bucket lookups.

Occurrences whose `asset.captured_at is None` are excluded from both charts (there's no time axis
position to place them at), the same exclusion `MostActiveMonthProvider`/`LongestStreakProvider`
already apply.

### Per-pet stacking within each species

For each species independently:

- Group confirmed `PetOccurrence` rows by `(season bucket, identity)`, counting occurrences per
  cell.
- Rank identities by total count across the whole displayed range; the top N (implementation
  detail, suggested 6 to match this app's existing validated categorical palette size from DT-1104)
  each get their own stacked band and a stable color; every other identity's counts are summed into
  a single "Other" band.
- Buckets are continuous from the species' earliest to latest confirmed-photo season (inclusive),
  zero-filled for any season in between with no confirmed photos for that species at all.
- A species with zero confirmed photos across the whole library renders its card's empty state
  instead of an empty chart (mirroring "Progress Over Time"'s `chartPasses.length === 0` empty
  state), e.g.: "No confirmed cat photos yet."

### Backend

New read-only endpoint(s) (exact shape left to implementation — one endpoint parameterized by
species, or one endpoint returning both species' timelines together, whichever keeps the query
count down) computing the above at read time from `PetOccurrence` joined to `Asset` and `Identity`,
following `MetricsService`'s existing "grouped query, not one query per identity" style (see
`_species_breakdown()`) rather than looping in Python per identity. No new table, no new column, no
change to the existing `/metrics` response shape.

### Frontend

`MetricsPage.tsx` gains two new `Card`s immediately after the existing "Progress Over Time" card
(after line ~401, before the closing `</section>`), each containing a new stacked-area chart
component parameterized by title, data, and top-N palette assignment so the same component serves
both "Dogs Over Time" and "Cats Over Time" rather than two near-duplicate implementations.

## Acceptance criteria

- Given confirmed dog photos in Winter 2025 (Dec 2025) and Winter 2026 (Jan/Feb 2026) for the same
  dog, "Dogs Over Time" buckets them together as one `"Winter 2025"` point, not two separate points.
- Given a dog with confirmed photos only in Spring 2026, "Dogs Over Time"'s X axis still includes
  Winter 2025 through Spring 2026 with the intervening seasons zero-filled, if any other dog has
  data in that range; a season with literally no confirmed dog photos across every dog is not
  rendered as a point at all (there's nothing to zero-fill against).
- Given more than N dogs with confirmed photos, the chart shows the top N by total volume as
  individually colored bands plus one combined "Other" band, and the "Other" band's height in each
  season equals the sum of every non-top-N dog's count that season.
- Given zero confirmed cat photos in the library, "Cats Over Time" renders an explanatory empty
  state instead of an empty/blank chart.
- Given a `PetOccurrence` whose `asset.captured_at` is `None`, it is excluded from both the season
  bucketing and any total-volume ranking used to pick the top N.
- Neither chart changes `_species_breakdown()`'s point-in-time totals, `_detection_coverage()`, or
  `ProgressOverTimeChart`'s existing per-pass rendering — all three are unchanged by this work.

## Open questions

- **One combined chart vs. two per-species charts, each stacked by pet identity**: resolved during
  scoping in favor of two per-species charts, each stacked by individual pet identity (top N +
  "Other") rather than one chart stacking "dog" vs. "cat" as its two bands. A combined chart would
  answer a coarser question (species mix over time) that this app's `_species_breakdown()` already
  answers as a point-in-time snapshot; two per-pet-stacked charts answer the more specific "which
  pets, and when" question this spec is actually after.
- Top-N cutoff (suggested 6) and tie-breaking when two identities are equally close to the cutoff
  are left to implementation, following the same "deterministic, documented, not a hidden
  configuration knob" bar this app already applies elsewhere (e.g. `BestFriendProvider`'s
  lowest-`identity_id` tiebreak).
- Whether the two new endpoint(s) should be folded into the existing `GET /metrics` response or
  live as new dedicated endpoint(s) fetched separately (like Insights' `/summary`, `/places`,
  `/people`, `/cards` split) is left to implementation. A dedicated endpoint keeps the always-loaded
  `/metrics` payload from growing with a query that's plausibly heavier (per-identity, per-season
  grouping) than everything else that endpoint currently returns.
