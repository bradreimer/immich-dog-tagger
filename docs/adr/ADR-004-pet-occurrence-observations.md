# ADR-004: Pet Occurrences as Observations, Not Conclusions

## Status
Accepted

## Context
Issue [#94](https://github.com/bradreimer/immich-dog-tagger/issues/94) asks for a "fun layer" on
top of confirmed pet identifications: favorite human, favorite places, travel history, and similar
derived summaries, combining `Identity`/`CropClassification` data the project already produces
with metadata Immich already computes per photo (capture time, GPS/location, recognized people).

The project's existing ground-truth-vs-derived-state philosophy (`docs/specs/v1.0.0.md` FR-4/FR-5,
`ADR-001`) already draws a hard line for classifications: a human review is authoritative input; a
classifier prediction is derived, reproducible state that must never be treated as if a human
confirmed it. The same question applies one layer up here: should "Hermann's favorite human is
Brad" be a fact Dog Tagger stores and later reads back, or a number it recomputes every time it's
asked?

Storing the conclusion directly (e.g. a `favorite_human_id` column on `Identity`) is tempting
because it's cheap to read. But it has the same failure mode the project already rejected for
classifications: it goes stale silently (a new batch of photos, or a single review correction,
changes the true answer without anyone updating the stored one), it has no explanation (there's no
way to show "112 photos with Brad" behind the label without recomputing it anyway), and it can't
be audited or safely recomputed if the ranking logic changes later.

## Decision
Persist only the underlying factual observations, and compute every conclusion at read time:

- `PetOccurrence` is a settled, per-(photo, pet) fact row — asset, identity, confidence, source,
  and provenance back to the `CropClassification` it was derived from. It is materialized (kept in
  sync) as a side effect of classification/review/reclassification settling an identity for a
  crop; nothing ever writes a `PetOccurrence` row directly from a UI action.
- Immich-provided per-photo facts needed for insights (GPS/location, recognized people, favorite
  flag) are cached on `Asset` itself, refreshed from the same Immich response the scanner already
  fetches. This is a cache of externally-sourced facts, not a Dog Tagger conclusion.
- `InsightsService` reads `PetOccurrence` + `Asset` and computes "favorite human," "favorite
  place," photo counts, and similar summaries fresh on every request. Nothing computed this way is
  ever written back into a table read by a later request — the computation is the only "storage."

This mirrors the classification/review split already in place: `CropClassification` is derived,
recomputable state; a `ReviewAction` is the one thing treated as authoritative input.
`PetOccurrence` plays the `CropClassification` role here — a settled fact, not a locked-in
conclusion — and there is deliberately no equivalent of a "confirmed favorite" a human can set,
because these are statistics about existing data, not new ground truth being introduced.

## Alternatives Considered
- **Store conclusions directly** (e.g. `favorite_human_id`/`favorite_place` columns on
  `Identity`). Rejected: goes stale on every new photo or correction without an explicit
  recompute step, loses the ability to show its own reasoning, and can't be recomputed
  retroactively if the ranking approach changes — the same problems the project already solved for
  classifications by keeping them derived.
- **Query Immich live for insights instead of caching.** Rejected: doesn't scale to a real
  library (a per-view API round trip), and would make Immich a second source of truth for
  application state, which `ADR-001` already rules out.
- **Precompute and cache insight results in a materialized table, invalidated on write.**
  Deferred, not rejected outright: adds real complexity (cache invalidation on every classification
  change) for a problem that doesn't exist yet at single-household library scale, where computing
  an identity's insights from its own occurrence rows is cheap. Revisit only with evidence it's
  needed.

## Consequences
Every derived insight is reproducible and explainable — "why is this the top place" always has an
answer, because the answer is the underlying rows, not a cached number. Adding a new insight (e.g.
a future "Best Friends" feature) is a new read-time query over existing facts, not a new column or
migration. The cost is that insight endpoints do real aggregation work per request rather than a
single-row lookup — acceptable at the scale this iteration targets (see
`docs/specs/v1.6-pet-insights.md` Non-goals on deferring a precomputed cache).
