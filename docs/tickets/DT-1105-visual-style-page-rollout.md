# DT-1105: Apply visual style to Mission Control, Metrics, Job Queue, and Review

## **ID**

DT-1105

## **Related spec**

[v1.2 Visual Style Refresh](../specs/v1.2-visual-style-refresh.md) -- FR-5, FR-6

## **Priority**

Medium

## **Status**

Completed

## **Goal**

Roll the DT-1104 foundations (sidebar shell, blue accent, status colors, `StatTile`) out to every
existing page, and add the Metrics page's donut and trend charts.

## **Context**

DT-1104 lands the primitives; this ticket consumes them so the whole app -- not just new
components -- matches the target style, and closes the spec's Metrics-charting requirement (FR-5)
using only fields `GET /metrics` already returns.

## **Implementation notes**

- Mission Control: job/review stat cards converted to `StatTile` (Active Jobs = info/blue,
  Completed = good, Failed = critical, Review Remaining = warning). Header gets Run Pipeline
  (primary) + Reclassify (outline) quick-action buttons calling the same `createJob()` path the
  existing Manual Operations card buttons use -- not a new code path. Removed the amber
  `rgba(...)` gradient hero card in favor of a flat card. Manual Operations, Automation
  Schedules, System Diagnostics, Recent Jobs, and `DogManagementCard` keep their existing
  structure/data, restyled only (flat cards, status-token colors for job-status badges).
- Metrics: added `DonutChart` (confident / review queue / unknown, status colors, legend + direct
  labels) and `PassTrendChart` (review-queue/confident/unknown on one shared axis, since all
  three are "count of eligible crops") built from `pass_history`; the existing
  labeled-example-count sparkline stayed a separate single-series chart rather than a second axis
  on the trend chart (dual-axis explicitly rejected per the spec's non-goals). Stat tiles
  (coverage, review rate, review queue, labeled examples, last reclassify) converted to
  `StatTile`. Automation-rate banner kept as the page's most prominent element, restyled without
  the amber gradient.
  Charts render nothing (not a broken chart) when `pass_history` has fewer than 2 entries, same
  guard the existing sparkline already used.
- Job Queue: `JobRow` status colors switched from ad-hoc `sky/emerald/rose/amber/zinc` Tailwind
  classes to the shared status tokens, so a given status renders identically here, on Mission
  Control's recent-jobs list, and on the Metrics donut.
- Review: wrapped in the new sidebar shell only. Left `ReviewCard` and its children, the filter
  buttons' behavior, `useReviewKeyboard`, and the correction/skip flow untouched -- only the
  surrounding chrome (shell, typography, button color via the token change) changed. Verified by
  exercising review (load queue, correct, skip, keyboard shortcuts) in a browser, not just diff
  inspection, per the spec's acceptance criteria.

## **Acceptance criteria**

- All four pages render inside the sidebar shell, light and dark.
- No page hardcodes an amber/orange accent value.
- Job status colors agree across Job Queue, Mission Control, and the Metrics donut.
- Metrics donut and trend charts render from live data and degrade gracefully below 2 passes.
- Review's correction/skip/keyboard workflow is unchanged, confirmed in a browser.
- `npm run build` and `npm run lint` pass.

## **Testing requirements**

- Manual visual verification of all four pages, light and dark, in an isolated scratch backend
  (no real Immich instance required -- empty/mocked state renders).
- Manual exercise of the Review workflow end to end (load, correct, skip, previous/next,
  keyboard shortcuts) to confirm no regression.

## **Dependencies**

DT-1104.

## **Suggested commit message**

`feat(DT-1105): roll out sidebar shell and stat/chart styling to all pages`
