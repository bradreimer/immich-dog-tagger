# DT-1002: Main-page Reclassify action

## **ID**

DT-1002

## **Related spec**

[v1.0.0 Product & Engineering Specification](../specs/v1.0.0.md) -- FR-4, primary workflow (section 1)

## **Priority**

High

## **Status**

Completed

## **Goal**

Expose a safe, understandable Reclassify workflow.

## **Context**

A backend Reclassify operation (DT-1001) is only useful to end users if it's reachable without a CLI. This ticket puts a "Reclassify" action on Mission Control next to the existing pipeline/sync actions, and pairs it with visibility into whether running it is worthwhile (delivered together with DT-1006's Learning Progress card).

## **Implementation notes**

- Added a "Reclassify with reviewed examples" entry to Mission Control's existing "Manual Operations" card, reusing the same `createJob`/`launching`-guard plumbing already used by "Process new photos" and "Sync" -- no new action-triggering code was needed since Reclassify is just another `PipelineOperation` (DT-1001).
- The card copy explicitly explains the guarantee that matters most to users: it never rescans/redownloads/redetects and never changes an already-confirmed label.
- Duplicate-submission guard: the existing `disabled={launching !== null}` on all manual-operation buttons already covers Reclassify; the backend's single-flight job lock (DT-1005) is the authoritative guard.
- "Show current job status" and "last completed pass" are satisfied by the new Learning Progress card (DT-1006), which sits directly below the operations card and shows the most recent Reclassify's status/timestamp/changed-count plus a coverage trend.
- No confirmation dialog was added: Reclassify is non-destructive by construction (it never touches reviewed ground truth), so a confirmation step would only slow down the review -> reclassify loop without protecting anything.
- Verified visually: built and ran the app locally, seeded sample data, and screenshotted Mission Control to confirm the button and status card render as intended.

## **Acceptance criteria**

- A user can run the full review -> reclassify loop without using a CLI or developer tooling.
- Duplicate submissions are guarded while a pass is running.
- Current job status and the last completed pass's outcome/timestamp are visible.
- The action explains that it applies reviewed examples to existing embeddings and never touches confirmed labels.

## **Testing requirements**

`npm run build` / `npm run lint`; manual visual verification via a local dev server + browser screenshot (no automated UI test framework exists in this project yet).

## **Dependencies**

DT-1001, DT-1005, DT-1006.

## **Suggested commit message**

`feat(DT-1002,DT-1006): add Reclassify action and learning-progress dashboard` (shipped in the same commit as DT-1006 -- see that ticket for why)
