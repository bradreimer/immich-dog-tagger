# DT-1011: v1.0.0 release validation

## **ID**

DT-1011

## **Related spec**

[v1.0.0 Product & Engineering Specification](../specs/v1.0.0.md) -- section 7 (Acceptance criteria), section 8 (Non-goals)

## **Priority**

High

## **Status**

Completed

## **Goal**

Verify the complete release against the specification.

## **Context**

DT-1000 through DT-1010 implement and document every v1.0.0 requirement individually. This ticket is the release gate: verify the assembled whole against the spec's acceptance criteria, close any release-blocking defects found, and tag the release only once everything passes.

## **Implementation notes**

Full report: [docs/validation/v1.0.0/DT-1011-release-validation.md](../validation/v1.0.0/DT-1011-release-validation.md). Summary:

- All 11 steps performed. `./scripts/check.sh` passes (257 tests, clean UI build/lint).
- Fresh-install, metrics, and restart/recovery were verified live against a running API instance on an isolated scratch database (not unit tests alone) -- including killing a simulated in-progress Reclassify and confirming both the job and its classification pass reconcile to `FAILED` on restart with a clear message.
- Version bumped to 1.0.0 (`pyproject.toml`, API app version) and release notes updated (`README.md` Project Status, `docs/roadmap.md`, `docs/status.md`).
- Two gaps disclosed rather than hidden: no live run against a real Immich library was performed (no credentials/GPU in this environment), matching the same disclosed gap from DT-1008. Every other acceptance criterion passed -- see the full criteria-by-criteria table in the report.

## **Acceptance criteria**

Every v1.0.0 acceptance criterion (spec section 7) is demonstrated and no release-blocking defects remain.

## **Testing requirements**

Full `./scripts/check.sh`, plus the manual verification steps in the report above.

## **Dependencies**

DT-1000 through DT-1010.

## **Suggested commit message**

`docs(release): v1.0.0 release validation`
