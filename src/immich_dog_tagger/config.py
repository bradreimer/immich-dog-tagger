"""
Application configuration.
"""

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

logger = logging.getLogger(__name__)


class ConfigError(Exception):
    """
    Raised when configuration (a ``CONFIG_FILE``, in practice) is present but invalid.

    Never raised for the legacy environment-variable path, which has no required fields --
    an unconfigured deployment produces an empty/default :class:`Config`, not an error.
    """


@dataclass(frozen=True)
class ImmichAccount:
    name: str
    api_key: str


@dataclass(frozen=True)
class Config:
    immich_url: str
    immich_api_key: str
    state_dir: Path
    cache_dir: Path
    yolo_model: Path
    crop_padding: float

    #: Browser-facing Immich base URL, for links a human clicks. Deployments where the
    #: container reaches Immich at a different address than the reviewer's browser (a
    #: Docker-internal hostname, say) set this; everyone else leaves it empty and gets
    #: ``immich_url``. Read through :attr:`immich_link_base_url`, never directly.
    immich_external_url: str = ""

    #: Request timeout (seconds) for the Immich API client. Bulk album/tag membership writes
    #: (issue #237) scale with the number of assets in an identity and can legitimately take
    #: Immich longer than httpx's 5s default to process, so this needs to be generous rather
    #: than left at the library default.
    immich_timeout_seconds: float = 60.0

    #: Every configured Immich account (today, from either a JSON ``CONFIG_FILE`` or the legacy
    #: ``IMMICH_API_KEY`` env var, which produces one implicit "default" account). Empty when
    #: nothing is configured yet. :attr:`immich_api_key` is a single-account convenience view
    #: over the first entry here for callers that don't yet need multi-account support -- see
    #: issue #346, which is the actual consumer of more than one account.
    accounts: tuple[ImmichAccount, ...] = ()

    @property
    def crop_dir(self) -> Path:
        return self.cache_dir / "crops"

    @property
    def immich_link_base_url(self) -> str:
        """
        Base URL for Immich deep links handed to the browser.
        """

        return self.immich_external_url or self.immich_url


def _immich_settings_from_env() -> tuple[
    str, str, float, str, tuple[ImmichAccount, ...]
]:
    """
    The legacy single-account configuration: ``IMMICH_URL``/``IMMICH_API_KEY``/
    ``IMMICH_EXTERNAL_URL``/``IMMICH_TIMEOUT_SECONDS`` environment variables.

    Returns ``(immich_url, immich_external_url, immich_timeout_seconds, immich_api_key,
    accounts)``.
    """

    immich_url = os.environ.get("IMMICH_URL", "")
    immich_api_key = os.environ.get("IMMICH_API_KEY", "")
    immich_external_url = os.environ.get("IMMICH_EXTERNAL_URL", "").strip()
    immich_timeout_seconds = float(os.environ.get("IMMICH_TIMEOUT_SECONDS", "60"))

    accounts = (
        (ImmichAccount(name="default", api_key=immich_api_key),)
        if immich_api_key
        else ()
    )

    return (
        immich_url,
        immich_external_url,
        immich_timeout_seconds,
        immich_api_key,
        accounts,
    )


def _immich_settings_from_file(
    path: Path,
) -> tuple[str, str, float, str, tuple[ImmichAccount, ...]]:
    """
    Structured configuration from a mounted JSON file (see docs/specs/json-config-file.md).

    Raises :class:`ConfigError`, naming ``path`` and the specific problem, for anything wrong
    with the file -- malformed JSON, a missing required field, or a duplicate account name.
    Never falls back to the legacy environment variables: a config file was clearly intended
    here, so a broken one is a startup failure, not a silent downgrade.
    """

    try:
        raw = path.read_text()
    except OSError as e:
        raise ConfigError(f"could not read config file {path}: {e}") from e

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ConfigError(f"config file {path} is not valid JSON: {e}") from e

    immich = data.get("immich") if isinstance(data, dict) else None
    if not isinstance(immich, dict):
        raise ConfigError(f'config file {path} is missing a top-level "immich" object')

    immich_url = immich.get("url")
    if not isinstance(immich_url, str) or not immich_url:
        raise ConfigError(f'config file {path} is missing required field "immich.url"')

    immich_external_url = str(immich.get("external_url") or "").strip()

    try:
        immich_timeout_seconds = float(immich.get("timeout_seconds", 60))
    except (TypeError, ValueError) as e:
        raise ConfigError(
            f'config file {path}: "immich.timeout_seconds" must be a number'
        ) from e

    raw_accounts = immich.get("accounts")
    if not isinstance(raw_accounts, list) or not raw_accounts:
        raise ConfigError(
            f'config file {path} must declare at least one account under "immich.accounts"'
        )

    accounts: list[ImmichAccount] = []
    seen_names: set[str] = set()

    for index, raw_account in enumerate(raw_accounts):
        if not isinstance(raw_account, dict):
            raise ConfigError(
                f"config file {path}: immich.accounts[{index}] must be an object"
            )

        name = raw_account.get("name")
        if not isinstance(name, str) or not name:
            raise ConfigError(
                f'config file {path}: immich.accounts[{index}] is missing "name"'
            )

        api_key = raw_account.get("api_key")
        if not isinstance(api_key, str) or not api_key:
            raise ConfigError(
                f'config file {path}: immich.accounts[{index}] ("{name}") is missing "api_key"'
            )

        if name in seen_names:
            raise ConfigError(
                f'config file {path}: duplicate account name "{name}" in immich.accounts'
            )

        seen_names.add(name)
        accounts.append(ImmichAccount(name=name, api_key=api_key))

    accounts = tuple(accounts)

    return (
        immich_url,
        immich_external_url,
        immich_timeout_seconds,
        accounts[0].api_key,
        accounts,
    )


def load_config(load_env_file: bool = True) -> Config:
    """
    Load application configuration.

    Immich connection settings (URL, timeout, accounts) come from the JSON file named by
    ``CONFIG_FILE``, when that path exists and is a file; otherwise they fall back to the
    legacy ``IMMICH_URL``/``IMMICH_API_KEY``/``IMMICH_EXTERNAL_URL``/``IMMICH_TIMEOUT_SECONDS``
    environment variables, unchanged from before this file-based path existed. Everything else
    (``STATE_DIR``, ``CACHE_DIR``, ``YOLO_MODEL``, ``CROP_PADDING``) always comes from
    environment variables -- see docs/specs/json-config-file.md for why.
    """

    if load_env_file:
        load_dotenv()

    state_dir = Path(
        os.environ.get(
            "STATE_DIR",
            "./state",
        )
    )

    cache_dir = Path(
        os.environ.get(
            "CACHE_DIR",
            "./cache",
        )
    )

    config_file = os.environ.get("CONFIG_FILE", "")
    config_path = Path(config_file) if config_file else None

    # `.is_file()` rather than `.exists()`: a Docker bind mount whose host source doesn't exist
    # yet gets auto-created as a directory, not a missing path -- treating that as "no config
    # file" keeps a not-yet-migrated deployment on the legacy env-var path with no error, per
    # FR-2/acceptance criteria, instead of a confusing IsADirectoryError.
    if config_path is not None and config_path.is_file():
        (
            immich_url,
            immich_external_url,
            immich_timeout_seconds,
            immich_api_key,
            accounts,
        ) = _immich_settings_from_file(config_path)

        legacy_immich_vars = (
            "IMMICH_URL",
            "IMMICH_API_KEY",
            "IMMICH_EXTERNAL_URL",
            "IMMICH_TIMEOUT_SECONDS",
        )
        if any(os.environ.get(var) for var in legacy_immich_vars):
            logger.warning(
                "Config file %s is present; legacy IMMICH_* environment variables are set but "
                "ignored.",
                config_path,
            )
    else:
        (
            immich_url,
            immich_external_url,
            immich_timeout_seconds,
            immich_api_key,
            accounts,
        ) = _immich_settings_from_env()

    return Config(
        immich_url=immich_url,
        immich_api_key=immich_api_key,
        accounts=accounts,
        immich_external_url=immich_external_url,
        immich_timeout_seconds=immich_timeout_seconds,
        state_dir=state_dir,
        cache_dir=cache_dir,
        yolo_model=Path(
            os.environ.get(
                "YOLO_MODEL",
                "/models/yolo11m.pt",
            )
        ),
        crop_padding=float(
            os.environ.get(
                "CROP_PADDING",
                "0.15",
            )
        ),
    )
