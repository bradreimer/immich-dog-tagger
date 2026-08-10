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
- DT-0907 live job progress
- DT-0908 CLI job runner integration

## Current Milestone
v0.9.4 Dynamic Dog Management

## Next Work
1. Implement dynamic dog identity persistence.
2. Add Mission Control dog management UI.
3. Remove hard-coded dog-name assumptions.
4. Keep release documentation aligned.

## Workflow Notes
- New features should begin with a spec in docs/specs/.
- Implementation-sized work should be captured in docs/tickets/.
- Documentation should be updated alongside code changes.

## Known Issues
- Some pipeline status counters may need future cleanup.
- Detection/classification status ownership needs review.
- Endpoint-level API auth is not implemented yet.
