# ADR-003: Automatic Temporal-Recency Classification

## Status
Accepted

## Context
DT-1114 (v1.4.0) gave each `Identity` an optional owner-set active date range
(`active_from`/`active_until`) and flagged, but never excluded, a candidate whose matched photo
fell outside it. This required the owner to maintain per-pet date ranges by hand, including
setting an end date when a pet passes away and a start date for a new pet -- exactly the
"visually similar individuals need a date signal to disambiguate" problem DT-1114 set out to
solve, but with a manual-upkeep cost that defeats the purpose for an owner who wants the tagger to
just work. The owner asked for the range to be inferred automatically from each identity's own
reference examples instead, using the photo being classified as the reference point rather than
wall-clock time -- so browsing old photos of a since-passed pet still classifies correctly, and a
new pet that looks like an old one is still told apart, without configuration.

`EmbeddingExample.captured_at` already exists and is already populated (from `Asset.captured_at`)
on every example created via bootstrap import or review correction (`Learner.learn_image`). No
new data collection is required -- only new use of data already stored.

## Decision
Remove `Identity.active_from`/`active_until` and the manual active-range API/UI entirely. Replace
the hard-boundary flag with continuous per-example recency weighting: `SimilarityScorer` computes
a `temporal_weight` (Gaussian decay, ~1 year characteristic scale, floor > 0, fail-open on a
missing date on either side) from the gap between the crop's own `captured_at` and each candidate
example's `captured_at`. `IdentityClassifier` picks each identity's best example, and ranks
candidates, by `similarity * temporal_weight` -- but continues to report that example's raw,
unweighted cosine similarity as the classification's confidence, so the temporal signal decides
*which* identity wins without manufacturing or distorting the confidence number itself (the same
constraint DT-1114's `date_conflict` already respected: surfaced alongside the match, never
folded into `similarity`).

See [docs/specs/v1.5-automatic-temporal-classification.md](../specs/v1.5-automatic-temporal-classification.md)
for the full requirements; this supersedes FR-4/FR-5 of
[docs/specs/v1.4-trustworthy-photo-library.md](../specs/v1.4-trustworthy-photo-library.md).

## Alternatives Considered
- **Keep manual ranges, improve the UI.** Rejected -- the owner explicitly asked to stop
  configuring this by hand; a better editing UI doesn't remove the upkeep burden.
- **Auto-suggest `active_from`/`active_until` from the earliest/latest reviewed example, but keep
  it as a stored, owner-confirmable range** (raised as an open question in v1.4's spec). Rejected
  for the first cut: a stored range is still a single hard boundary per identity, which doesn't
  degrade gracefully -- a pet photographed sporadically across decades would need the range to
  stay wide open, defeating disambiguation, while a range narrow enough to disambiguate risks
  hard-excluding a legitimate late/early photo. Continuous per-example weighting handles both a
  wide-spanning single identity and a tight disambiguation window without a stored boundary to
  keep in sync.
- **Weight by wall-clock recency (how long ago *now*) instead of proximity to the photo's own
  capture date.** Rejected -- it would make classifying an old photo (e.g. importing a
  years-old backlog) systematically favor whichever identity happens to have the most recent
  examples today, regardless of which identity was actually alive/present when that old photo was
  taken. Anchoring to the photo's own date is what makes browsing a deceased pet's old photos
  still work correctly.
- **Hard-exclude low-weight candidates instead of only re-ranking.** Rejected for this pass,
  consistent with DT-1114's original flag-only choice -- excluding outright removes the
  visual-similarity evidence entirely on a case where the classifier might still be right (e.g. a
  legitimately late or early photo of a long-lived pet), trading a milder problem (occasional
  wrong auto-pick, still reviewable) for a harder one (silently wrong "unknown").

## Consequences
- Classification behavior can now change for an identity purely based on when its labeled
  examples were captured relative to the photo being classified -- previously irrelevant unless
  the owner had set a range. This is the intended behavior, but it means classification quality
  now depends more on `Asset.captured_at` being populated (already the common case via Immich's
  `fileCreatedAt`) and on the reference set covering an identity's full timespan, not just its
  outdated appearance.
- `state.db` loses the `active_from`/`active_until` columns; no migration path is provided for
  existing installs carrying data in them (accepted -- the field had a single consumer, and the
  owner starts fresh).
- The `date-conflict` review reason is replaced by `temporal-mismatch`, so any saved filters,
  dashboards, or documentation referring to the old name need updating (tracked alongside this
  change, not left stale).
- `changed_count` in a Reclassify pass summary may rise the first time this ships, since
  identities can now flip when the new weighting picks a different best example than pure
  similarity did -- expected, not a regression.
