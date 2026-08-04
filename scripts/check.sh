#!/usr/bin/env bash

set -euo pipefail

echo "==> Python checks"
uv run ruff check --fix .
uv run ruff format
uv run pytest -q

echo "==> UI checks"
(
  cd ui
  npm run build
  npm run lint
)

echo "==> All checks passed"