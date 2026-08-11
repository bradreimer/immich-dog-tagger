# TICKET 09: End-to-end and regression test suite

## Goal
Protect the review-driven learning loop.

## Required scenarios
1. Fresh project with zero labels.
2. Initial pipeline.
3. Review one item.
4. Review 50-100 items.
5. Reclassify.
6. Verify reviewed labels remain unchanged.
7. Verify predictions update where expected.
8. Reclassify twice with unchanged inputs and verify stable results.
9. Add more reviews and reclassify again.
10. Failed/retried job.
11. Existing project upgrade/migration.
12. Zero labeled examples.
13. Missing/invalid embedding.
14. Unknown/low-confidence classification.

## Done when
The critical user journey is covered by automated tests and passes on a clean environment.
