# Current Status

## Completed
- Detection pipeline
- Classification pipeline
- Review queue API
- React review interface
- Correction workflow
- Skip workflow
- Review action tracking
- API hardening and review service-boundary cleanup
- Learning and review statistics
- DT-0901 through DT-0944 (job system, scheduling, backup/recovery, production validation, dynamic dog management -- v0.9.0 through v0.9.4)
- DT-1000 v1.0.0 architecture audit
- DT-1004 centralized nearest-neighbor classifier policy
- DT-1001 reclassification service/job
- DT-1003 review-to-example ground-truth hardening (fixed a real leakage defect)
- DT-1005 job lifecycle/idempotency/recovery for Reclassify
- DT-1002 + DT-1006 Reclassify action and Learning Progress dashboard
- DT-1007 pipeline/correction lifecycle logging
- DT-1008 scale validation (fixed two N+1 defects; documented gap: no literal 30k-image run performed in this environment)
- DT-1009 end-to-end review-driven learning loop test suite
- DT-1010 v1.0 user and operator documentation (docs/workflow.md)
- DT-1011 v1.0.0 release validation (see docs/validation/v1.0.0/DT-1011-release-validation.md)
- DT-1103 dedicated Metrics tab, next to Mission Control
- DT-1101 per-pass labeled-example-count/review-queue-size snapshots
- DT-1102 reconciled review-queue metric and prominent automation-rate metric
- DT-1104 visual style foundations: blue accent tokens, validated status/categorical palette,
  sidebar navigation shell, stat-tile primitive
- DT-1105 rolled the visual style out to all four pages, including Metrics' donut and trend
  charts
- DT-1106 UX review follow-ups: destructive-button contrast fix, relative "last updated" time,
  Mission Control next-action banner, Metrics automation trend delta
- DT-1107 moved dog management to its own `/dogs` page and sidebar tab
- DT-1108 consolidated Metrics' trend section into one dual-axis Progress Over Time chart
- DT-1109 fixed a 500 on `POST /classifications/{id}/correct` (raw ORM object with a binary
  embedding column was reaching FastAPI's JSON encoder)

## Current Milestone
v1.2 Visual Style Refresh -- all backlog tickets implemented (DT-1104 through DT-1108). Not yet
version-bumped or tagged. See [docs/specs/v1.2-visual-style-refresh.md](specs/v1.2-visual-style-refresh.md).
v1.1 Automation Coverage Dashboard is also complete (DT-1101, DT-1102, DT-1103; see
[docs/specs/v1.1-automation-coverage-dashboard.md](specs/v1.1-automation-coverage-dashboard.md)) and not yet version-bumped or tagged either.

## Next Work
Decide whether/when to cut a release covering v1.1+v1.2; next candidates beyond that are improved
reference-example selection, reference-set curation workflows, and confidence analysis (see
docs/roadmap.md "Active Learning Improvements").

## Workflow Notes
- New features should begin with a spec in docs/specs/.
- Implementation-sized work should be captured in docs/tickets/.
- Documentation should be updated alongside code changes.

## Known Issues
- Some pipeline status counters may need future cleanup.
- Detection/classification status ownership needs review.
- Endpoint-level API auth is not implemented yet.
- DT-1008's scale validation used synthetic-scale regression tests rather than a literal 30,000-real-image run (no GPU/Immich instance in the development environment); a real-library run is recommended before relying on it at that scale in production.
