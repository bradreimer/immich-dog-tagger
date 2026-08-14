# Copilot Instructions for Immich Dog Tagger

## Development workflow
- Prefer spec-driven and ticket-driven development.
- Before implementing a meaningful feature or behavior change, check the relevant spec in docs/specs/ and the related ticket in GitHub Issues.
- If no matching spec or ticket exists, create one before coding (issues use the "User Story", "Bug Report", or "Feature Request" templates in `.github/ISSUE_TEMPLATE/`).
- Keep the documentation package in sync with implementation decisions, architecture changes, and release progress.

## Required documentation artifacts
- Use docs/project-overview.md for project context.
- Use docs/roadmap.md for planning and release scope.
- Use docs/specs/ for behavioral intent and acceptance criteria.
- Use GitHub Issues for implementation-sized work with clear scope and validation steps.
- Use docs/adr/ for significant architectural decisions.

## Implementation expectations
- Prefer small, focused changes with tests.
- Link changes back to the relevant ticket or spec in commit messages and summaries when possible.
- Update docs/status.md and the relevant spec/ticket when progress changes.

## Validation
- Run the relevant tests before considering work complete.
- For Python changes, use uv run pytest and the Ruff checks.
- For UI changes, run the Vite build and lint checks.
