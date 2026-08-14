# Development Workflow

## Flow

Idea
 -> Specification
 -> Ticket
 -> Implementation
 -> Tests
 -> Documentation Update
 -> Commit
 -> Release

## Commits

Prefer:
- small focused commits
- descriptive commit messages
- one logical change per commit

Examples:
feat(review): add review queue statistics
fix(api): handle missing crop image

## Before starting work
- Review the relevant spec in docs/specs/.
- Review or create a ticket as a GitHub Issue, using the template that matches the work: "User
  Story" (`.github/ISSUE_TEMPLATE/user_story.md`), "Bug Report"
  (`.github/ISSUE_TEMPLATE/bug_report.md`), or "Feature Request"
  (`.github/ISSUE_TEMPLATE/feature_request.md`) for an unscoped idea.
- Update docs/status.md if the milestone or priorities change.

## Testing

Before commits:
- uv run ruff check --fix .
- uv run ruff format
- uv run pytest -q

UI changes:
- npm run build
- npm run lint

## Releases

A release should have:
- completed tickets
- passing tests
- updated documentation
- release tag
