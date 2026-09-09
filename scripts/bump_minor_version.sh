#!/usr/bin/env bash
# Bumps pyproject.toml's [project].version to the next minor release (X.Y.Z -> X.(Y+1).0)
# and regenerates uv.lock so its self-referential version entry stays in sync.
#
# Run this as part of a PR that implements a new feature (a "User Story" issue) --
# see docs/specs/feature-pr-version-bump.md.

set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

current_version=$(grep -m1 '^version = "' pyproject.toml | sed -E 's/^version = "(.*)"$/\1/')

if [[ ! "${current_version}" =~ ^([0-9]+)\.([0-9]+)\.([0-9]+)$ ]]; then
  echo "error: pyproject.toml version '${current_version}' is not X.Y.Z" >&2
  exit 1
fi

major="${BASH_REMATCH[1]}"
minor="${BASH_REMATCH[2]}"
new_version="${major}.$((minor + 1)).0"

sed -i.bak -E "s/^version = \"${current_version}\"$/version = \"${new_version}\"/" pyproject.toml
rm -f pyproject.toml.bak

if command -v uv >/dev/null 2>&1; then
  uv lock
else
  echo "warning: uv not found on PATH -- run 'uv lock' manually to sync uv.lock" >&2
fi

echo "Bumped version: ${current_version} -> ${new_version}"
