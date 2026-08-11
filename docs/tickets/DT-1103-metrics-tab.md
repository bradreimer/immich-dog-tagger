# DT-1103: Move Learning Progress into a dedicated Metrics tab

## **ID**

DT-1103

## **Related spec**

[v1.1 Automation Coverage Dashboard](../specs/v1.1-automation-coverage-dashboard.md)

## **Priority**

Medium

## **Status**

Pending

## **Goal**

Give metrics their own top-level page instead of sharing space with Mission Control's operational controls or the Review workspace.

## **Context**

DT-1006 put the "Learning Progress" card on Mission Control, next to job controls and diagnostics. Operator feedback: metrics deserve their own tab, separate from both Mission Control (operational actions) and Review (the correction workflow) -- Mission Control gets noisier as more operational cards accumulate, and a dedicated page gives the trend data (about to grow further per DT-1101/DT-1102) room to breathe without crowding the manual-operations card.

## **Acceptance criteria**

- A new top-level "Metrics" tab exists in the app's navigation (`Header.tsx`'s `links` array), following the existing `Mission Control` / `Job Queue` / `Review` pattern (same pushState-based routing already used by those).
- A new `MetricsPage` (`ui/src/features/metrics/`) renders everything currently in Mission Control's Learning Progress card: confident coverage, review rate, labeled examples, last-Reclassify status, and the coverage sparkline.
- The Learning Progress card is removed from `MissionControlPage.tsx` -- moved, not duplicated. Mission Control keeps only its operational cards (jobs, diagnostics, manual operations, schedules).
- Review is unaffected; metrics never appear there either.
- The new page fetches from the existing `GET /metrics` endpoint (`getLearningMetrics()` in `ui/src/lib/api.ts`) -- no new API needed for this ticket specifically.

## **Testing requirements**

`npm run build` / `npm run lint`; manual visual verification via a local dev server + browser screenshot of both Mission Control (card gone) and the new Metrics tab (card present and functional), following the same verification approach used for DT-1002/DT-1006.

## **Dependencies**

DT-1006 (relocates what it built). Independent of DT-1101/DT-1102, but DT-1102 depends on this landing first since it updates the relocated page rather than Mission Control.

## **Suggested commit message**

`feat(DT-1103): move Learning Progress into a dedicated Metrics tab`
