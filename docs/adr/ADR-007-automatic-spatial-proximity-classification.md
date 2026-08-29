# ADR-007: Automatic Spatial-Proximity Classification

## Status
Accepted

## Context
ADR-003 (v1.5.0) taught `IdentityClassifier` to weigh how closely a candidate reference example's
own `captured_at` aligns with the photo being classified, breaking near-ties between visually
similar identities in favor of the temporally closer one. The owner observed the same problem
recurs for location: two dogs that look alike are often photographed in different characteristic
places (different homes, different regular walk routes), and location is frequently exactly the
cue a human reviewer reaches for to tell them apart.

`Asset.latitude`/`longitude` already exist and are already populated from Immich's EXIF GPS data
(issue #94, added for the read-only Pet Insights "Places" view), but `EmbeddingExample` -- the
reference set classification compares against -- has no location column, and nothing in
`scoring.py`/`classifier.py` uses location at all.

## Decision
Add `latitude`/`longitude` to `EmbeddingExample`, denormalized from the source `Asset` at learn
time exactly as `captured_at` already is. `SimilarityScorer` gains a `spatial_weight` (Gaussian
decay over haversine distance, a few-kilometer characteristic scale, floor > 0, fail-open on a
missing coordinate on either side) computed the same way `temporal_weight` is. `IdentityClassifier`
ranks candidates, and picks each identity's best example, by
`similarity * temporal_weight * spatial_weight` -- but continues to report that example's raw,
unweighted cosine similarity as the classification's confidence, so neither signal manufactures or
distorts the confidence number itself (the same constraint `temporal_weight` already respects).

This is deliberately not a new mechanism: it reuses v1.5's exact shape (continuous per-example
weighting, multiplicative combination, fail-open, ranking-only, no owner configuration) applied to
a second, independent axis of evidence. The two weights compose by simple multiplication rather
than any more elaborate scheme, so an example that is both temporally and spatially misaligned is
discounted more than one that is only misaligned on one axis, and either an exact time match or an
exact location match is not enough on its own to overrule a large mismatch on the other axis.

See [docs/specs/v1.9-automatic-spatial-classification.md](../specs/v1.9-automatic-spatial-classification.md)
for the full requirements.

## Alternatives Considered
- **Use the cached reverse-geocoded `country`/`state`/`city` fields (issue #94) instead of raw
  lat/long distance.** Rejected -- coarse administrative boundaries produce a hard edge (two
  photos a mile apart but across a state/country line score as totally different; two photos a
  hundred miles apart in the same state score as identical), whereas continuous distance decays
  smoothly and needs no geocoding dependency. The geocoded fields remain Insights-only.
- **A single combined "context" weight instead of separate temporal and spatial weights.** Rejected
  -- keeping them as two independent multiplicative factors (as `MatchScore`/`ClassificationCandidate`
  already do for time) preserves each one's own transparency (a stored candidate still shows
  exactly why it was down-weighted) and lets a future signal be added the same way without
  reworking existing ones.
- **Hard-exclude candidates below a spatial threshold instead of only re-ranking.** Rejected for
  the same reason ADR-003 rejected it for time: excluding outright removes visual-similarity
  evidence entirely on a case the classifier might still be right about (e.g. a legitimately
  far-from-home photo, like a trip or a vet visit), trading a milder problem (occasional wrong
  auto-pick, still reviewable) for a harder one (silently wrong "unknown").
- **An owner-tunable decay scale from the start.** Rejected for this pass, matching v1.5's own
  choice -- ship one sane default as a code constant, revisit if real usage shows it doesn't fit a
  particular library (open question carried into the spec).

## Consequences
- Classification behavior can now change for an identity purely based on where its labeled
  examples were captured relative to the photo being classified -- previously irrelevant. This is
  the intended behavior, but classification quality for this signal now depends on
  `Asset.latitude`/`longitude` being populated (only true when Immich has GPS EXIF data for a
  photo -- commonly absent for scanned prints, screenshots, or photos with location services off)
  and on the reference set covering an identity's typical locations, not just one.
- `state.db` gains `embedding_examples.latitude`/`longitude` via an additive migration; existing
  examples simply have no location on this signal (`NULL`), the same fail-open outcome as a
  missing `captured_at` -- no destructive change and no forced fresh-database restart, unlike
  ADR-003's migration.
- `changed_count` in a Reclassify pass summary may rise the first time this ships, for the same
  reason ADR-003's did: identities can flip when the new weighting picks a different best example
  than similarity-and-time alone did.
- A `location-mismatch` review reason is added alongside `temporal-mismatch`; any saved filters,
  dashboards, or documentation enumerating review reasons need to account for the new value.
