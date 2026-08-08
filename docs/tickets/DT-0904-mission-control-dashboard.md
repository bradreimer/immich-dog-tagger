# DT-0904

## ID
DT-0904

## Related spec
v0.9.0 Mission Control Foundation

## Priority
High

## Status
Completed

## Goal
Make Mission Control the web application's operational landing page.

## Context
The existing review UI is one part of the product. The user should land on a dashboard that summarizes pipeline activity and provides access to operations.

## Implementation notes
- Inspect the existing React routing, layout, components, styling, and API client.
- Add a Mission Control page without disrupting the existing Review workflow.
- Show current pipeline/job state, recent jobs, and entry points to operational views.
- Keep the visual language consistent with the existing UI.

## Acceptance criteria
- Mission Control is the application landing page.
- Current operational state is visible.
- Recent jobs are visible.
- Review remains reachable.
- Existing UI functionality is preserved.

## Testing requirements
- Component/page tests consistent with the existing UI test strategy.
- Build and lint must pass.

## Dependencies
DT-0903

## Suggested commit message
`feat(ui): add mission control dashboard`
