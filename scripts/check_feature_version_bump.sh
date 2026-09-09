#!/usr/bin/env bash
# CI check: a PR that closes a "user-story"-labeled issue must bump pyproject.toml's minor
# version relative to the PR's base commit. See docs/specs/feature-pr-version-bump.md.
#
# Required env vars: GH_TOKEN, REPO (owner/repo), PR_BODY, BASE_SHA.

set -euo pipefail

read_version() {
  grep -m1 '^version = "' "$1" | sed -E 's/^version = "(.*)"$/\1/'
}

major_of() {
  echo "$1" | cut -d. -f1
}

minor_of() {
  echo "$1" | cut -d. -f2
}

issue_numbers=$(grep -oiE '(close[sd]?|fix(e[sd])?|resolve[sd]?)[[:space:]]+#[0-9]+' <<<"${PR_BODY:-}" \
  | grep -oE '[0-9]+' || true)

if [[ -z "${issue_numbers}" ]]; then
  echo "No closing issue reference found in PR body -- version bump not required."
  exit 0
fi

requires_bump=0
for issue_number in ${issue_numbers}; do
  labels=$(gh api "repos/${REPO}/issues/${issue_number}" --jq '.labels[].name' 2>/dev/null || true)
  if grep -qx "user-story" <<<"${labels}"; then
    echo "Issue #${issue_number} is labeled user-story -- version bump required."
    requires_bump=1
  fi
done

if [[ "${requires_bump}" -eq 0 ]]; then
  echo "No closed issue is labeled user-story -- version bump not required."
  exit 0
fi

head_version=$(read_version pyproject.toml)
base_version=$(git show "${BASE_SHA}:pyproject.toml" | read_version /dev/stdin)

bumped=0
if [[ "$(major_of "${head_version}")" -gt "$(major_of "${base_version}")" ]]; then
  bumped=1
elif [[ "$(major_of "${head_version}")" -eq "$(major_of "${base_version}")" ]] \
  && [[ "$(minor_of "${head_version}")" -gt "$(minor_of "${base_version}")" ]]; then
  bumped=1
fi

if [[ "${bumped}" -eq 0 ]]; then
  echo "::error::This PR closes a user-story issue but pyproject.toml's minor version" \
    "(${base_version} -> ${head_version}) was not bumped. Run scripts/bump_minor_version.sh" \
    "and commit the result."
  exit 1
fi

echo "Version bumped: ${base_version} -> ${head_version}. OK."
