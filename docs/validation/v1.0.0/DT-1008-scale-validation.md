# DT-1008: 30,000-Image Scale Validation

## What was actually run

This environment has no GPU and no real Immich instance, so a literal end-to-end
30,000-real-image run was not executed. What was validated is the *shape* of the
resource behavior that determines whether a 30,000-image project stays bounded:
query-count independence from row count, and batched (not all-at-once) processing.
That's covered by automated regression tests in `tests/test_scale.py`, at a reduced
synthetic scale (hundreds of rows), since that's sufficient to prove or disprove
O(1)-vs-O(n) query behavior without a multi-minute CI run.

Anyone validating an actual 30,000-image production library should re-run the
`immich-dog-tagger pipeline` and Reclassify against that library and compare
against the expectations below; this is explicitly called out as a gap in
[DT-1011: v1.0.0 release validation](https://github.com/bradreimer/immich-dog-tagger/issues/56).

## N+1 defects found and fixed

1. **`IdentityClassifier.classify()`** re-queried the entire `EmbeddingExample`
   table (joined to `Identity`) on *every call*. Since `ClassificationService` and
   `ReclassifyService` both call `classify()` once per crop, classifying 30,000
   crops issued 30,000 identical queries. Fixed by caching the loaded example list
   for the classifier instance's lifetime (`classifier.py::_load_examples`) --
   callers already create one `IdentityClassifier` per classify/reclassify run, so
   this changes the cost from O(crops) queries to O(1).
2. **`ReviewQueryService.classifications()`/`active_review()`** lazy-loaded
   `crop` and `matched_example.identity` per row with no eager-loading, so
   building a page of N review items issued roughly 2N extra queries. Fixed with
   `selectinload`/`contains_eager` so the query count is constant regardless of
   page size.

## Batching

- Reclassify (`services/reclassify.py`) loads only crop *ids* up front (cheap:
  30,000 integers is a few hundred KB), then processes and commits in batches of
  200 (configurable), so the working set held in memory/uncommitted-transaction at
  any moment is one batch, not the whole archive. A crash mid-run preserves
  already-committed batches (see DT-1005).
- `/review` defaults to a 50-item page and `/jobs` caps at 500; neither endpoint
  can return the full archive in one response. Metrics (`/metrics`) returns only
  aggregate counts, never per-crop records.

## Documented operational expectations for a 30,000-image project

- **Database growth**: `crop_classifications` gains one row per detected dog crop
  (not per photo). `classification_passes` gains one small row per Reclassify run
  regardless of archive size.
- **Reclassify cost**: dominated by (a) computing embeddings for crops that don't
  have one cached yet -- a one-time cost per crop, since the embedding is cached
  on `CropClassification.embedding` after the first classify or reclassify -- and
  (b) O(examples) cosine-similarity comparisons per crop. Re-running Reclassify
  after the initial pass with unchanged inputs is cheap: no embedding recomputation.
- **Memory**: bounded by batch size (default 200 crops in flight), not archive size.
- **Browser**: never receives more than one page (`/review` default 50,
  `/jobs` max 500) or aggregate counts (`/metrics`) at a time.

## Status
Completed. Two real N+1 defects were found and fixed with regression coverage;
a live 30,000-real-image run was not performed in this environment and is
flagged as an open item for DT-1011 release validation against a real library.
