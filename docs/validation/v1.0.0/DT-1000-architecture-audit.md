# DT-1000: v1.0.0 Architecture Audit

## Inventory vs. v1.0.0 requirements

| Requirement | State | Notes |
|---|---|---|
| FR-1 Project bootstrap | Implemented | `create_database` initializes fresh state; existing installs preserved across restarts (`_ensure_identity_activation_column` pattern). |
| FR-2 Pipeline (scan/download/detect/embed/classify) | Implemented | `PipelineService`, `PipelineJobRunner`, per-stage handlers in `services/job_execution.py`. Progress/status already exposed via `PipelineJob`. |
| FR-3 Review persistence | Partial | `ClassificationCorrectionService.correct()` + `Learner.learn_image()` upsert by `(identity, crop_path)`, but re-reviewing a crop under a **different** identity leaves the stale example under the old identity (leakage). No test covers this. |
| FR-4 Reclassify | Missing | No service recomputes predictions from existing embeddings/examples without touching download/detect. `ClassificationMode.ALL` exists but overwrites **every** classification including `MANUAL`/`REVIEW` sources — unsafe to reuse for Reclassify as-is. |
| FR-5 Classification semantics / centralized policy | Partial | Threshold (`0.80`) and candidate limit are duplicated as literals in `classifier.py`, `services/classification.py`, `services/review_query.py`, `cli.py`, `services/job_execution.py`. No persisted classifier/config version. |
| FR-6/FR-7 Metrics & dashboard | Partial | `StatusService` exposes raw counts; no coverage/review-rate ratios, no pass history, no "last reclassification" concept (because passes don't exist yet). |
| FR-8 Observability | Partial | Job failures are persisted (`error_message`) and diagnostics endpoint exists, but there is no structured start/end/duration logging around classification/reclassification. |
| FR-9 Performance | Partial | `/review` and `/jobs` are already paginated/limited. `ReviewQueryService` lazy-loads `crop`/`detection`/`matched_example` per item (N+1 risk at scale). No embedding reuse/caching exists — every classify pass re-embeds from the image file. |
| FR-10 Documentation | Missing | No v1.0 user workflow doc yet. |

## Reusable building blocks (do not recreate)

- **Job system** (`PipelineJob`, `PipelineJobRunner`, `PipelineJobRepository/Service`, `PipelineJobDispatcher`, `job_recovery.recover_interrupted_jobs`) already gives queued/running/completed/failed states, single-flight execution (`has_running_job`), and startup recovery of interrupted jobs. Reclassify should be added as a new `PipelineOperation` handled through this same system rather than a bespoke runner.
- **`IdentityClassifier`** already does nearest-neighbor + candidate ranking; it just needs its threshold/decision logic centralized instead of recreated.
- **`Learner`** already has upsert-by-path dedup; it needs a "supersede other identities for this path" step to close the FR-3 leakage gap, not a rewrite.
- **Mission Control page** (`ui/src/features/mission-control/MissionControlPage.tsx`) already has a "Manual Operations" card pattern (`full_pipeline`, `sync`) that Reclassify should extend, and a diagnostics card that the metrics/trend UI should sit beside.

## Current nearest-neighbor decision threshold

Lives as the literal `0.80` in five places (see table above). `IdentityClassifier.classify(embedding, threshold=0.80, candidate_limit=3)` is the actual decision point: identity is assigned only when the best cosine-similarity candidate is `>= threshold`; otherwise the result is `identity=None` ("Unknown"). This becomes the single `ClassifierPolicy` in `src/immich_dog_tagger/policy.py`.

## Required schema migrations

Additive only (follows the existing `_ensure_identity_activation_column` pattern in `database.py` — no destructive edits):

1. `crop_classifications.classifier_version` (nullable string) — policy version stamped at (re)classification time.
2. `crop_classifications.classification_pass_id` (nullable FK) — which pass last touched an AUTO prediction.
3. `crop_classifications.embedding` (nullable blob) — cached crop embedding so Reclassify does not recompute OpenCLIP features for crops that already have one.
4. New table `classification_passes` — pass/job-scoped run record (status, counts, classifier version, timestamps, error).

## Smallest implementation path for remaining requirements

1. **DT-1004** — `src/immich_dog_tagger/policy.py` (`ClassifierPolicy`, `ClassificationDecision`), consumed by `IdentityClassifier`, `ClassificationService`, `ReviewQueryService._review_reason`, `cli.py`, `job_execution.py`. No new files beyond the policy module.
2. **DT-1001** — new `services/reclassify.py` (`ReclassifyService`) that: skips entirely if no active labeled examples exist; only updates `CropClassification` rows with `source == AUTO`; reuses `embedding` column when present; batches commits; writes a `ClassificationPass` row. Wired in as `PipelineOperation.RECLASSIFY` in `job_execution.py` so it inherits job lifecycle/locking/recovery for free (closes DT-1005 for this operation).
3. **DT-1003** — `Learner.relearn_image()` (delete same-path examples under other identities before upserting), called from `ClassificationCorrectionService.correct()`.
4. **DT-1002** — extend the existing Mission Control "Manual Operations" card + a small "Learning Progress" card; reuse `createJob`/`getJobs` plumbing already in `ui/src/lib/api.ts`.
5. **DT-1006** — `services/metrics.py` (or extend `StatusService`) + `/metrics` route + UI card with a compact pass-history sparkline.
6. **DT-1007** — `logging.getLogger(__name__)` calls at classify/reclassify/correction start-end, counts/durations/ids only.
7. **DT-1008** — eager-load relationships in `ReviewQueryService` queries, batch/commit reclassify in chunks, add a synthetic-scale regression test.
8. **DT-1009/1010/1011** — additive tests and docs; final tag gated on `./scripts/check.sh` plus the v1.0.0 acceptance criteria.

## Status
Completed — see ticket implementations DT-1001 through DT-1011 for delivery of the items marked Partial/Missing above.
