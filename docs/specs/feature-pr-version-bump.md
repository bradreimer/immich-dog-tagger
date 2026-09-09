# Feature PR Minor Version Bump

## Purpose

The app's displayed version (`immich_dog_tagger.version.get_version()`, surfaced in the sidebar
and Settings page) comes from `pyproject.toml`'s `[project].version`. That number only moves when
someone remembers to edit it by hand, so it has drifted out of sync with what's actually shipped
(most bug-fix PRs land with no version change at all, and past minor bumps were done ad hoc as
part of writing up a roadmap milestone). Make the bump part of shipping a feature, not a separate
step someone has to remember.

## User story

As a maintainer, I want the PR that implements a new feature (a "User Story" issue) to bump the
project's minor version automatically as part of CI, so the version shown in the running app,
`pyproject.toml`, and the docs always reflect what has actually shipped, without relying on
memory.

## Goals

- A PR that closes a `user-story`-labeled issue bumps `pyproject.toml`'s minor version
  (`X.Y.Z` -> `X.(Y+1).0`) as part of that PR.
- The app needs no separate code change to pick up the new version -- `get_version()` already
  reads it from installed package metadata, which is populated from `pyproject.toml`.
- The bump is paired with a `docs/roadmap.md` entry for the new version and a `docs/status.md`
  entry for the issue, continuing the project's existing documentation convention.
- CI catches a feature PR that forgot the bump, instead of relying on review.

## Non-goals

- Bumping for `bug`-labeled or unscoped `enhancement`-labeled issues. A bug fix is not a new
  minor version; an unscoped feature request isn't implementation-ready yet (per
  `CONTRIBUTING.md`, it must first be split into a `user-story`/`bug` issue).
- Major or patch version semantics, changelog generation, or release-tag automation --
  out of scope; see
  [docs/specs/deployment-release-automation.md](deployment-release-automation.md) for the
  broader release process.
- Enforcing the bump for PRs that don't close any issue (direct small fixes/docs, per
  `CONTRIBUTING.md`'s "Before you start").

## Requirements

- A helper script (`scripts/bump_minor_version.sh`) bumps `pyproject.toml`'s version consistently
  (minor +1, patch reset to 0) and regenerates `uv.lock` so both stay in sync -- no hand-editing
  the version string in two places.
- A CI check runs on every pull request: it reads the issue numbers the PR body closes (`Closes
  #N` / `Fixes #N` / `Resolves #N`), and if any of those issues carries the `user-story` label,
  it requires `pyproject.toml`'s minor version on the PR head to be greater than on the PR's base
  commit. It fails with a message pointing at `scripts/bump_minor_version.sh` when the bump is
  missing.
- A PR with no closing reference to a `user-story` issue is unaffected by the check.
- `CONTRIBUTING.md` and `docs/development-workflow.md` document the convention so it isn't only
  discoverable by reading CI config.

## Acceptance criteria

- Given a PR whose body contains `Closes #N` where issue `#N` is labeled `user-story`, and
  `pyproject.toml`'s minor version is unchanged from the base branch, the CI check fails with a
  message naming the missing bump.
- Given the same PR after running `scripts/bump_minor_version.sh` and committing the result, the
  CI check passes.
- Given a PR closing only a `bug`-labeled issue, the check passes with no version change required.
- Given a PR with no closing reference at all, the check passes with no version change required.
- Running `scripts/bump_minor_version.sh` twice in a row without an intervening edit produces two
  sequential minor bumps (e.g. `1.12.0` -> `1.13.0` -> `1.14.0`), never a no-op.

## Open questions

- A PR that closes more than one `user-story` issue only needs one bump, not one per issue --
  this spec treats that as the expected case and doesn't special-case it further.
