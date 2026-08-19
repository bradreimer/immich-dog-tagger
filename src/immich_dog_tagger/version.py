"""Single source of truth for the running application version.

Reads from installed package metadata (populated from `pyproject.toml` at build/install
time) instead of duplicating the version string as a separate literal.

The Docker image bakes in the short commit it was built from via the `GIT_COMMIT`
environment variable (set from a build arg in `Dockerfile`, populated by CI on every
push to `main` — see `.github/workflows/docker-publish.yml`). When present, it's
appended as a PEP 440 local version segment, e.g. `1.7.0+a1b2c3d`, so a running
container's version string identifies the exact commit it shipped from. A `docker
build` without the arg (or a non-Docker install) simply omits the segment.
"""

import os
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _installed_version

_FALLBACK_VERSION = "0.0.0-dev"
_COMMIT_SHA_LENGTH = 7


def get_version() -> str:
    try:
        base_version = _installed_version("immich-dog-tagger")
    except PackageNotFoundError:
        base_version = _FALLBACK_VERSION

    commit = os.environ.get("GIT_COMMIT", "").strip()
    if commit:
        return f"{base_version}+{commit[:_COMMIT_SHA_LENGTH]}"
    return base_version
