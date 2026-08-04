#!/usr/bin/env bash

set -euo pipefail

echo "==> Installing Python dependencies"
uv sync

echo "==> Installing UI dependencies"
(
  cd ui
  npm ci
)

echo "==> Bootstrap complete"