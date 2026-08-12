# DT-1000: v1.0.0 release plan and architecture audit

## **ID**

DT-1000

## **Related spec**

[v1.0.0 Product & Engineering Specification](../specs/v1.0.0.md)

## **Priority**

High

## **Status**

Completed

## **Goal**

Map the current implementation to the v1.0.0 specification before changing code.

## **Context**

v1.0.0 adds Reclassify, a centralized classifier policy, ground-truth hardening, metrics, and observability/scale work on top of an already-substantial pipeline and job system. Before writing any code, the project needed a clear map of what already satisfies each v1.0.0 requirement, what's reusable, and what's genuinely missing, so the implementation tickets that follow have concrete file/module targets instead of re-deriving architecture from scratch.

## **Implementation notes**

- Inventoried pipeline stages, review persistence, the embedding store, the classifier, the database schema, the job system, and the web routes/components against every v1.0.0 functional requirement (FR-1 through FR-10), marking each implemented/partial/missing.
- Identified reusable building blocks that later tickets should extend rather than recreate: the `PipelineJob` system, `IdentityClassifier`, `Learner`, and the Mission Control "Manual Operations" card pattern.
- Documented the required additive schema migrations (`classifier_version`, `classification_pass_id`, `embedding` on `CropClassification`; a new `classification_passes` table) and the smallest implementation path for each remaining ticket.
- Full findings recorded in [docs/validation/v1.0.0/DT-1000-architecture-audit.md](../validation/v1.0.0/DT-1000-architecture-audit.md).

## **Acceptance criteria**

- A short architecture map exists.
- Every v1.0.0 functional requirement is marked implemented/partial/missing.
- Implementation tickets have clear file/module targets.
- Required schema migrations are identified.
- The current nearest-neighbor decision threshold and every location it lives in are documented.

## **Testing requirements**

Documentation-only ticket; no code changed. Confirmed `./scripts/check.sh` was green before starting.

## **Dependencies**

None.

## **Suggested commit message**

`docs(DT-1000): complete v1.0.0 architecture audit`
