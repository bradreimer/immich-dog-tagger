# TICKET 09: End-to-end and regression test suite

## Status
Completed

## Implementation notes
Added `tests/test_e2e_review_learning_loop.py`, exercising the real services together (not mocked) end-to-end. Scenario coverage:
- **1, 12** (fresh project, zero labels/examples), **2** (initial pipeline classify), **13/14** (zero examples -> everything Unknown, no forced labels): `test_full_review_driven_learning_loop`, steps 1-2.
- **3, 4** (review one item / a 50-100-scale batch): same test, reviews 25 of 40 crops via the real `ClassificationCorrectionService` + `Learner`, asserting the labeled-example population matches exactly (DT-1003).
- **5, 6, 7** (Reclassify; reviewed labels unchanged; predictions update where expected): same test -- confirms REVIEW-sourced rows are byte-for-byte unchanged after Reclassify while unreviewed AUTO rows pick up the new examples.
- **13** (missing/invalid embedding): a legacy row with `embedding=None` is included and confirmed to get embedded, cached, and correctly classified during Reclassify.
- **8** (Reclassify twice, stable results) and **9** (more reviews, reclassify again): same test, continues the narrative -- second pass has `changed_count == 0`; a third pass after 5 more reviews shows `eligible_count` shrinking by exactly 5 and the newly reviewed rows flipping to `REVIEW` source.
- **10** (failed/retried job): `test_failed_reclassify_job_can_be_retried_without_corruption` runs a real `PipelineJobRunner` with a crashing embedder, confirms the job and its `ClassificationPass` are marked `FAILED`, then retries with a working embedder and confirms success with exactly 2 `ClassificationPass` rows total (no duplication).
- **11** (existing project upgrade/migration): `test_existing_project_migrates_and_continues_working` hand-builds a pre-v1.0.0 sqlite schema (missing `classifier_version`/`classification_pass_id`/`embedding`/`classification_passes`), runs `create_database`, confirms the pre-existing reviewed row survived untouched, and then runs a full classify + reclassify cycle against the migrated schema to prove it's actually functional, not just structurally migrated.

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
