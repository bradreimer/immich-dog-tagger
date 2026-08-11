# TICKET 01: Reclassification service/job

## Goal
Implement a backend reclassification operation that reuses stored embeddings and current reviewed examples.

## Steps
1. Add a project-scoped reclassification service using the existing classifier.
2. Load only valid labeled examples and eligible crops.
3. Batch nearest-neighbor work.
4. Preserve authoritative reviewed labels.
5. Persist prediction, score, decision state, classifier/config version, and pass/job ID.
6. Make repeated execution idempotent.
7. Handle zero-example projects cleanly.
8. Record counts, duration, and failure details.

## Done when
The service can safely reclassify an existing project without scanning, downloading, detecting, or recomputing already-valid embeddings.
