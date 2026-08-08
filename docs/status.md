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
- DT-0901 persistent pipeline job model
- DT-0902 pipeline job runner
- DT-0903 jobs API
- DT-0904 mission control dashboard
- DT-0905 job queue UI
- DT-0906 manual pipeline controls

## Current Milestone
v0.5.0 Review Workflow Stabilization

## Next Work
1. Display learning progress in UI.
2. Improve review batch controls.
3. Improve embedding example management.
4. Document release workflow.

## Workflow Notes
- New features should begin with a spec in docs/specs/.
- Implementation-sized work should be captured in docs/tickets/.
- Documentation should be updated alongside code changes.

## Known Issues
- Some pipeline status counters may need future cleanup.
- Detection/classification status ownership needs review.
- Endpoint-level API auth is not implemented yet.
