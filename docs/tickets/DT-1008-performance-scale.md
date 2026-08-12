# DT-1008: 30,000-image scale validation

## **ID**

DT-1008

## **Related spec**

[v1.0.0 Product & Engineering Specification](../specs/v1.0.0.md) -- FR-9, acceptance criteria (30,000-image dry run)

## **Priority**

Medium

## **Status**

Completed (with a documented gap -- see Implementation notes)

## **Goal**

Validate that v1.0 can operate on a large archive without browser or server resource blowups.

## **Context**

v1.0.0's acceptance criteria require bounded resource behavior at 30,000-image scale. This environment has no GPU and no real Immich instance, so validation focused on finding and fixing the query-count and batching defects that would actually cause unbounded behavior, backed by synthetic-scale regression tests, rather than a literal large real-image run.

## **Implementation notes**

Full detail in [docs/validation/v1.0.0/DT-1008-scale-validation.md](../validation/v1.0.0/DT-1008-scale-validation.md). Summary:

- Found and fixed two real N+1 defects: `IdentityClassifier.classify()` re-querying the full example table once per crop (fixed with per-instance caching), and `ReviewQueryService` lazy-loading `crop`/`matched_example.identity` per row (fixed with `selectinload`/`contains_eager`).
- Confirmed batching: Reclassify processes/commits in bounded batches (200 by default) rather than holding the whole archive in memory or one transaction.
- Confirmed pagination: `/review` (50 default) and `/jobs` (500 max) already bound payload size; `/metrics` returns aggregates only.
- Gap, disclosed rather than hidden: a literal 30,000-real-image run was not executed. The N+1 fixes and batching are covered by synthetic-scale regression tests (`tests/test_scale.py`) that prove the query-count-independent-of-row-count and bounded-batch properties instead. Flagged as an open item for DT-1011.

## **Acceptance criteria**

- A representative workload completes, or can be processed in bounded batches, with documented resource behavior.
- Obvious N+1 database access is found and fixed.
- The browser never receives the full archive in one payload.

## **Testing requirements**

`tests/test_scale.py` (query-count-independent-of-row-count regressions for the classifier and review queue; batched-reclassify-at-scale correctness).

## **Dependencies**

DT-1001, DT-1004.

## **Suggested commit message**

`perf(DT-1008): fix two N+1 query defects, document scale expectations`
