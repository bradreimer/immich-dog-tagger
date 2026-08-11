# TICKET 02: Main-page Reclassify action

## Status
Completed

## Implementation notes
- Added a "Reclassify with reviewed examples" entry to Mission Control's existing "Manual Operations" card, reusing the same `createJob`/`launching`-guard plumbing already used by "Process new photos" and "Sync" -- no new action-triggering code was needed since Reclassify is just another `PipelineOperation` (DT-1001).
- The card copy explicitly explains the guarantee that matters most to users: it never rescans/redownloads/redetects and never changes an already-confirmed label.
- Duplicate-submission guard: the existing `disabled={launching !== null}` on all manual-operation buttons already covers Reclassify; the backend's single-flight job lock (DT-1005) is the authoritative guard.
- "Show current job status" and "last completed pass" are satisfied by the new Learning Progress card (DT-1006), which sits directly below the operations card and shows the most recent Reclassify's status/timestamp/changed-count plus a coverage trend.
- No confirmation dialog was added: Reclassify is non-destructive by construction (it never touches reviewed ground truth), so a confirmation step would only slow down the review -> reclassify loop without protecting anything.
- Verified visually: built and ran the app locally, seeded sample data, and screenshotted Mission Control to confirm the button and status card render as intended.

## Goal
Expose a safe, understandable Reclassify workflow.

## Steps
1. Add a Reclassify action to the project main page.
2. Disable or guard duplicate submissions while a pass is running.
3. Show current job status and progress/counts where available.
4. Explain that Reclassify applies reviewed examples to existing embeddings.
5. Show success/failure state and the timestamp of the last completed pass.
6. Add confirmation only if the operation is sufficiently expensive in the current architecture.

## Done when
A user can run the full review -> reclassify loop without using a CLI or developer tooling.
