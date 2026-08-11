# TICKET 08: 30,000-image scale validation

## Status
Completed (with a documented gap -- see below)

## Implementation notes
See [docs/validation/v1.0.0/DT-1008-scale-validation.md](../validation/v1.0.0/DT-1008-scale-validation.md) for full detail. Summary:
- Found and fixed two real N+1 defects: `IdentityClassifier.classify()` re-querying the full example table once per crop (fixed with per-instance caching), and `ReviewQueryService` lazy-loading `crop`/`matched_example.identity` per row (fixed with `selectinload`/`contains_eager`).
- Confirmed batching: Reclassify processes/commits in bounded batches (200 by default) rather than holding the whole archive in memory or one transaction.
- Confirmed pagination: `/review` (50 default) and `/jobs` (500 max) already bound payload size; `/metrics` returns aggregates only.
- Gap, disclosed rather than hidden: this environment has no GPU and no real Immich instance, so a literal 30,000-real-image run was not executed. The N+1 fixes and batching are covered by synthetic-scale regression tests (`tests/test_scale.py`) that prove the query-count-independent-of-row-count and bounded-batch properties instead. Flagged as an open item for DT-1011.

## Goal
Validate that v1.0 can operate on a large archive without browser or server resource blowups.

## Steps
1. Build a representative load-test dataset or fixture.
2. Measure memory and runtime for scan, embedding reuse, and reclassification.
3. Verify batching and pagination.
4. Find and fix obvious N+1 database access.
5. Ensure the browser never receives the full archive in one payload.
6. Establish documented operational expectations for a 30,000-image project.

## Done when
A representative 30,000-image workload completes or can be processed in bounded batches with documented resource behavior.
