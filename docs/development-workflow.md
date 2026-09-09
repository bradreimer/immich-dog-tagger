# Development workflow

## Flow

Idea → spec → ticket → implementation → tests → documentation update → commit → release

## Before starting work

- Check [docs/specs/](specs/) for a spec covering the change. Write one first if it affects
  user-facing behavior, workflow, or cross-cutting architecture.
- Check GitHub Issues for a matching ticket, or open one with the template that fits: "User
  Story" (`.github/ISSUE_TEMPLATE/user_story.md`), "Bug Report"
  (`.github/ISSUE_TEMPLATE/bug_report.md`), or "Feature Request"
  (`.github/ISSUE_TEMPLATE/feature_request.md`) for an idea that isn't scoped yet.
- Update [docs/status.md](status.md) if this changes the current milestone or priorities.

## Commits

Small, focused, one logical change per commit:

```text
feat(review): add review queue statistics
fix(api): handle missing crop image
```

## Testing

Before committing:

```bash
uv run ruff check --fix .
uv run ruff format
uv run pytest -q
```

For UI changes:

```bash
npm run build
npm run lint
```

## Feature version bump

A PR that closes a `user-story`-labeled issue must bump the project's minor version
(`pyproject.toml`'s `[project].version`, `X.Y.Z` -> `X.(Y+1).0`) as part of that PR --
run `./scripts/bump_minor_version.sh` and commit the result. The running app reads its version
from `pyproject.toml` directly (`immich_dog_tagger.version.get_version()`), so no separate
app-side edit is needed. CI enforces this for any PR closing a `user-story` issue; bug fixes and
PRs with no closing issue reference are unaffected. See
[docs/specs/feature-pr-version-bump.md](specs/feature-pr-version-bump.md).

## Releases

A release needs: its tickets completed, tests passing, documentation updated, and a release tag.
