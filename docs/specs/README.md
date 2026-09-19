# Specs

This directory holds product and behavioral specifications for major project capabilities.

Use a spec when a change affects user-facing behavior, workflow design, or cross-cutting architecture.

## Template
- Purpose
- User story
- Goals
- Non-goals
- Requirements
- Acceptance criteria
- Open questions

## New ideas belong in GitHub Issues, not new files here

An idea that hasn't been scoped yet -- a bug report, a rough feature idea, a "we should improve
X" -- belongs in a [GitHub Issue](https://github.com/bradreimer/immich-dog-tagger/issues) (the
"Bug Report" or "Feature Request" template), not a new markdown file in this directory. Write a
spec here only once there's a concrete, user-facing or cross-cutting capability to scope for
implementation, per [CLAUDE.md](../../CLAUDE.md)'s workflow.

Every spec should be linked from the GitHub Issue that tracks its implementation (the "User
Story"/"Bug Report" templates' "Related spec" field). A spec with no linked issue is dead weight --
either open the issue that implements it, or remove the spec. Ticket tracking itself lives entirely
in GitHub Issues; see [docs/tickets/README.md](../tickets/README.md).
