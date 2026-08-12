# Display Learning Progress

ID: TICKET-002

Related Spec: Learning System

Priority: Medium

Status: Complete

## Goal
Show learning progress in the browser UI.

## Acceptance Criteria
Users can see review and learning progress.

## Implementation Notes
Delivered by DT-1006 as the "Learning Progress" card on Mission Control: confident coverage, review rate, labeled-example count, the most recent Reclassify's status/timestamp/changed-count, and a compact coverage-trend sparkline across recent classification passes. See [DT-1006](DT-1006-metrics-dashboard.md) and `ui/src/features/mission-control/MissionControlPage.tsx`.

## Suggested Commit Message
feat(ui): display learning progress summary
