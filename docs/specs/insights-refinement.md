# Insights Refinement: Dedup, New Cards, Honest Top Photos

Tracking issue: [#269](https://github.com/bradreimer/immich-dog-tagger/issues/269).

## Purpose

v1.6.0 ([#94](https://github.com/bradreimer/immich-dog-tagger/issues/94),
[docs/specs/v1.6-pet-insights.md](v1.6-pet-insights.md)) shipped `favourite place` and
`favourite human` as stat tiles on the Insights page. v1.7.0
([docs/specs/v1.7-pluginable-insights.md](v1.7-pluginable-insights.md), [ADR-005](../adr/ADR-005-insight-provider-plugin-architecture.md))
migrated the *computation* behind those two facts onto the new `InsightProvider` mechanism, but
left an explicit open question unresolved: whether the migrated providers should *also* render as
cards on the new `/insights/cards` feed, or stay exclusively in the `/insights/summary` stat tiles.
The implementation shipped both — `InsightsSummary.top_place`/`top_person` (stat tiles) and
`FavouritePlaceProvider`/`FavouriteHumanProvider` (cards) now render the identical fact twice on
the same page.

Separately, `InsightsService.top_photos()` ranks by raw `PetOccurrence.confidence` with no source
filter. `ClassificationCorrectionService.correct()` and manual detection assignment both write
`confidence = 1.0` whenever a human sets an identity (`ClassificationSources.REVIEW`/`MANUAL`), so
"Top photos" is currently just "photos a human tagged," not "photos the classifier was most sure
about" — the section's stated purpose.

This spec closes v1.7's open question (one home per fact, not two), lands four of the insight
providers v1.6/v1.7 deferred, and fixes Top Photos to rank by genuine classifier confidence.

## User story

As an owner viewing a dog or cat's Insights page, I want each fact shown exactly once, so the page
isn't repeating itself with two different labels for the same number.

As an owner viewing Top Photos, I want to see the photos the classifier was most confident about on
its own, so the section tells me something about classifier quality instead of just echoing photos
I already reviewed.

As an owner, I want more of the fun facts this app already has the data for (favourite time period,
photo streaks, a best-friend pet, year-over-year activity), so Insights keeps growing the way
ADR-005 intended: one provider at a time, no frontend rework per fact.

## Goals

- Resolve v1.7's deferred "one home or two" question: each fact appears in exactly one place on the
  Insights page.
- Add four new `InsightProvider`s from the v1.6/v1.7 deferred list (minus "first photo", out of
  scope for this iteration):
  - **Most active month** — the single calendar month (e.g. "March 2024") with the most confirmed
    photos for this identity.
  - **Longest streak** — the longest run of consecutive days with at least one confirmed photo.
  - **Best friend** — the other identity (dog or cat) this one co-occurs with most often in the
    same confirmed photos. This is v1.6/v1.7's deferred "Best Friends" item, and the first real use
    of the `InsightScope.LIBRARY` escape hatch the protocol already reserves for it.
  - **Year over year** — confirmed-photo count this calendar year vs. the same identity's count last
    calendar year.
- Fix `top_photos()` to rank only classifier-original confidence, so a human decision never crowds
  out a genuine high-confidence auto-classification.
- Keep every new provider computed at read time from existing `PetOccurrence`/`Asset` data, per
  ADR-004 — no schema change, no stored conclusion, `None` (never a fabricated placeholder) when an
  identity doesn't have enough data yet.

## Non-goals

- "First photo" (earliest confirmed occurrence) — explicitly excluded from this iteration.
- On This Day, Pet World Tour map — still deferred, unchanged from v1.7.
- Any change to `timeline`/`places`/`people` (full ranked lists) — unaffected.
- A materialized/precomputed insights or co-occurrence cache. Best Friend runs its own bounded
  `LIBRARY`-scope query per request, same as `places()`/`people()` already do (ADR-005's
  Consequences already anticipates this).
- Changing what `ClassificationCorrectionService.correct()` writes. Human decisions keep recording
  `confidence = 1.0`/`source = REVIEW` exactly as today — this spec only changes how `top_photos()`
  *reads* that data, not what gets written.

## Requirements

### Dedup favourite place / favourite human

Pick the card feed (`/insights/cards`, `FavouritePlaceProvider`/`FavouriteHumanProvider`) as the one
home, and remove `top_place`/`top_person` from `InsightsSummary` and the two corresponding
`StatTile`s in `DogInsightsPage.tsx`. Rationale: ADR-005's whole premise is that a new fact needs no
frontend change beyond the one-time card grid; keeping a second, bespoke stat-tile path for exactly
two facts works against that, and every future fact in this spec (month, streak, best friend,
year-over-year) is shipping as a card, not a new stat tile. `InsightsSummary` keeps
`total_photos`/`first_seen`/`last_seen`/`photos_by_year`/`favorite_photo_count` — those are
structural counts other providers already depend on, not opinionated facts themselves (unchanged
from v1.7).

### New providers

All four follow the existing `InsightProvider` protocol (`services/insights/providers.py`) and are
added to `INSIGHT_PROVIDERS`, matching `TotalPhotosMilestoneProvider`'s existing shape:

- `MostActiveMonthProvider` (`scope=IDENTITY`, `category="time"`): group this identity's
  occurrences by `(asset.captured_at.year, asset.captured_at.month)`, return the largest group as
  `value="March 2024"`, `subtext="N photos"`. `None` if no occurrence has a `captured_at`.
- `LongestStreakProvider` (`scope=IDENTITY`, `category="time"`): distinct capture dates sorted,
  longest run where each date is exactly one day after the previous. `value="14 days"`,
  `subtext="<start date> – <end date>"`. `None` below a 2-day streak (a single day isn't a
  "streak").
- `BestFriendProvider` (`scope=LIBRARY`, `category="social"`): given this
  identity's occurrence asset IDs, query `PetOccurrence` for other identities sharing those same
  `asset_id`s, same species-agnostic co-occurrence Places/People already allow; the identity with
  the highest shared-asset count wins. `value="<name>"`, `subtext="N photos together"`. `None` if no
  other identity ever co-occurs.
- `YearOverYearProvider` (`scope=IDENTITY`, `category="volume"`): current calendar year's confirmed
  count vs. the prior calendar year's, both already available via the same grouping
  `InsightsSummary.photos_by_year` uses. `value` names the direction and delta (e.g. "+8 photos vs.
  last year" / "-3 photos vs. last year"). `None` if the prior calendar year has zero confirmed
  photos (nothing to compare against — not "+N vs. 0", which reads as manufactured).

### Top Photos ranks genuine confidence only

`InsightsService.top_photos()` filters to `occurrence.source == ClassificationSources.AUTO` before
sorting by `-confidence`, excluding `REVIEW`/`MANUAL` occurrences (both always `confidence == 1.0`
by construction, per `correction.py`). If an identity has zero `AUTO` occurrences (everything it has
was manually tagged), `top_photos()` returns an empty list — this is a real, distinct state from "no
confirmed photos yet" (`summary.total_photos == 0`), so `DogInsightsPage.tsx`'s empty-state copy for
this section is updated to say so (e.g. "No auto-classified photos yet — every confirmed photo here
was manually tagged.") rather than reusing "No confirmed photos yet."

## Acceptance criteria

- Given an identity with a favourite place and favourite human, the Insights page shows each fact
  exactly once (as a card), not as both a stat tile and a card.
- Given an identity with confirmed photos in only one calendar month, `MostActiveMonthProvider`
  returns that month; given photos spread with no `captured_at` data at all, it returns `None` and
  no card appears.
- Given an identity with confirmed photos on 5 consecutive calendar days and no other run longer,
  `LongestStreakProvider` returns "5 days" with the correct date range.
- Given two identities that co-occur in 12 shared confirmed photos (their highest shared count each
  has with any other identity), `BestFriendProvider` returns the other identity's name and "12
  photos together" for both.
- Given an identity with photos confirmed in the prior calendar year and none yet this year,
  `YearOverYearProvider` reports the decrease; given zero photos in the prior calendar year, it
  returns `None`.
- Given an identity whose confirmed photos are a mix of `AUTO` and `REVIEW`/`MANUAL` sources,
  `top_photos()`'s ranking includes only `AUTO` occurrences, ordered by their own confidence.
- Given an identity whose confirmed photos are *entirely* `REVIEW`/`MANUAL`, `top_photos()` returns
  an empty list and the UI shows the new "no auto-classified photos yet" message, not "no confirmed
  photos yet."
- All four new providers return `None` (no card, never a placeholder) for an identity with
  insufficient data, matching ADR-004.

## Open questions

- `BestFriendProvider` ties (two other identities sharing the same highest co-occurrence count):
  this spec doesn't mandate a tiebreak rule beyond "pick one deterministically" (e.g. lowest
  `identity_id`) — left to implementation, consistent with how `place_counts`/`person_counts`
  already resolve ties via `Counter.most_common()`'s stable order.
- Whether `MostActiveMonthProvider` should aggregate by calendar month across all years (e.g. "most
  photos taken in any July") instead of one specific year-month instance is left to implementation;
  this spec specifies the year-month-instance version as it mirrors `TotalPhotosMilestoneProvider`'s
  existing "which specific photo/month" style.
