# Browser Review UX Improvements

## Purpose
Make browser-based review workflows faster, clearer, and less error-prone.

## User Story
As a reviewer, I want clear progress and low-friction controls so I can process review queues efficiently.

## Goals
- Reduce interaction cost for common review actions.
- Improve clarity of loading, error, and completion states.
- Keep progress context visible during review.

## Non-goals
- Full visual redesign of the entire product.
- New non-review product surfaces.
  **Amended** (see [v1.4-trustworthy-photo-library.md](v1.4-trustworthy-photo-library.md)): a mock
  user interview found that "process a review queue" isn't the owner's actual mental model --
  they want a persistent, searchable library of classified photos, with the queue as one filtered
  view within it rather than the only surface. The queue and this spec's improvements to it
  remain valid and unchanged; a new library surface is added alongside it, superseding this
  non-goal specifically.

## Requirements
- Primary review actions must remain accessible via keyboard and pointer.
- Progress indicators must remain visible and accurate after actions.
- Filtering and queue navigation must be predictable.
- Empty/error states must include clear recovery actions.

## Acceptance Criteria
- Reviewers can complete common flows with fewer clicks/steps.
- Progress and queue state remain accurate after correct/skip actions.
- UI behavior for loading/error/empty states is test-covered.

## Open Questions
- Should per-identity progress breakdown be part of v0.9.0 or a follow-up?
