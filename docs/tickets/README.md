# Tickets

Ticket-tracking moved from this directory to
[GitHub Issues](https://github.com/bradreimer/immich-dog-tagger/issues) so that ticket state
(open/closed, labels, search) is native instead of hand-maintained in markdown. The historical
tickets that used to live here (`DT-0901`-`DT-1118`, `TICKET-001`-`TICKET-003`) were migrated to
closed GitHub Issues, one per ticket, preserving the original content -- see the repository's
closed issues for that history.

Use an issue when there is a clear scope, acceptance criteria, and test plan. Open one with the
template that matches the work:

- **User Story** (`.github/ISSUE_TEMPLATE/user_story.md`) -- a scoped, implementation-ready
  user-facing capability. Carries the fields this directory's tickets used: Related spec,
  Priority, Story, Context, Implementation notes, Acceptance criteria, Out of scope, Testing
  requirements, Dependencies, Suggested commit message.
- **Bug Report** (`.github/ISSUE_TEMPLATE/bug_report.md`) -- a defect, with reproduction steps,
  expected/actual behavior, and the same acceptance-criteria/testing/commit-message fields.
- **Feature Request** (`.github/ISSUE_TEMPLATE/feature_request.md`) -- an unscoped idea; refine it
  into a spec and a User Story issue before implementation.

The issue number is the ticket ID (no more hand-assigned `DT-XXXX`/`TICKET-XXX` numbers) --
reference it in commits, e.g. `fix(review): handle missing crop image` with `Closes #123` in the
commit body.
