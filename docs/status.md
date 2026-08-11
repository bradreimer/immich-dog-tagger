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

## Current Milestone
v1.0.0 (see [docs/specs/v1.0.0.md](specs/v1.0.0.md))

## Next Work
1. DT-1011: release validation against the full v1.0.0 acceptance criteria.
2. Tag v1.0.0 once DT-1011 passes.

## Workflow Notes
- New features should begin with a spec in docs/specs/.
- Implementation-sized work should be captured in docs/tickets/.
- Documentation should be updated alongside code changes.

## Known Issues
- Some pipeline status counters may need future cleanup.
- Detection/classification status ownership needs review.
- Endpoint-level API auth is not implemented yet.
- DT-1008's scale validation used synthetic-scale regression tests rather than a literal 30,000-real-image run (no GPU/Immich instance in the development environment); a real-library run is recommended before relying on it at that scale in production.
