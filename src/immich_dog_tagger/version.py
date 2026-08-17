"""Single source of truth for the running application version.

Reads from installed package metadata (populated from `pyproject.toml` at build/install
time) instead of duplicating the version string as a separate literal.
"""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _installed_version

_FALLBACK_VERSION = "0.0.0-dev"


def get_version() -> str:
    try:
        return _installed_version("immich-dog-tagger")
    except PackageNotFoundError:
        return _FALLBACK_VERSION
