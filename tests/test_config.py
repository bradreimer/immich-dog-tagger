import json
from pathlib import Path

import pytest

from immich_dog_tagger.config import ConfigError, load_config


def test_default_configuration(monkeypatch):
    monkeypatch.delenv("IMMICH_URL", raising=False)
    monkeypatch.delenv("IMMICH_EXTERNAL_URL", raising=False)
    monkeypatch.delenv("IMMICH_API_KEY", raising=False)
    monkeypatch.delenv("STATE_DIR", raising=False)
    monkeypatch.delenv("CACHE_DIR", raising=False)

    config = load_config(load_env_file=False)

    assert config.immich_url == ""
    assert config.immich_api_key == ""
    assert config.state_dir == Path("./state")
    assert config.cache_dir == Path("./cache")


def test_configuration_from_environment(monkeypatch):
    monkeypatch.setenv(
        "IMMICH_URL",
        "https://immich.example.com",
    )
    monkeypatch.setenv(
        "IMMICH_API_KEY",
        "secret",
    )
    monkeypatch.setenv(
        "STATE_DIR",
        "/tmp/state",
    )
    monkeypatch.setenv(
        "CACHE_DIR",
        "/tmp/cache",
    )

    config = load_config(load_env_file=False)

    assert config.immich_url == "https://immich.example.com"
    assert config.immich_api_key == "secret"
    assert config.state_dir == Path("/tmp/state")
    assert config.cache_dir == Path("/tmp/cache")


def test_cache_dir(monkeypatch):
    monkeypatch.setenv(
        "CACHE_DIR",
        "/tmp/cache",
    )

    config = load_config(load_env_file=False)

    assert config.cache_dir == Path("/tmp/cache")
    assert config.crop_dir == Path("/tmp/cache/crops")


def test_config_separates_state_and_cache(monkeypatch):
    monkeypatch.setenv("STATE_DIR", "/tmp/state")
    monkeypatch.setenv("CACHE_DIR", "/tmp/cache")

    config = load_config(load_env_file=False)

    assert config.state_dir == Path("/tmp/state")
    assert config.cache_dir == Path("/tmp/cache")
    assert config.crop_dir == Path("/tmp/cache/crops")


def test_immich_external_url_defaults_to_the_api_url(monkeypatch):
    monkeypatch.setenv("IMMICH_URL", "http://immich-server:2283")
    monkeypatch.delenv("IMMICH_EXTERNAL_URL", raising=False)

    config = load_config(load_env_file=False)

    assert config.immich_external_url == ""
    assert config.immich_link_base_url == "http://immich-server:2283"


def test_immich_external_url_overrides_the_browser_facing_link(monkeypatch):
    monkeypatch.setenv("IMMICH_URL", "http://immich-server:2283")
    monkeypatch.setenv("IMMICH_EXTERNAL_URL", "https://immich.example.com")

    config = load_config(load_env_file=False)

    # The API base is untouched -- only the link the browser follows changes.
    assert config.immich_url == "http://immich-server:2283"
    assert config.immich_link_base_url == "https://immich.example.com"


def test_blank_immich_external_url_falls_back_to_the_api_url(monkeypatch):
    monkeypatch.setenv("IMMICH_URL", "http://immich-server:2283")
    monkeypatch.setenv("IMMICH_EXTERNAL_URL", "   ")

    config = load_config(load_env_file=False)

    assert config.immich_link_base_url == "http://immich-server:2283"


def test_immich_timeout_seconds_defaults_to_a_generous_value(monkeypatch):
    monkeypatch.delenv("IMMICH_TIMEOUT_SECONDS", raising=False)

    config = load_config(load_env_file=False)

    assert config.immich_timeout_seconds == 60.0


def test_immich_timeout_seconds_reads_from_environment(monkeypatch):
    monkeypatch.setenv("IMMICH_TIMEOUT_SECONDS", "120")

    config = load_config(load_env_file=False)

    assert config.immich_timeout_seconds == 120.0


def _write_config_file(tmp_path: Path, data: dict) -> Path:
    path = tmp_path / "config.json"
    path.write_text(json.dumps(data))
    return path


def test_config_file_exposes_multiple_accounts_with_no_legacy_api_key(
    monkeypatch, tmp_path
):
    monkeypatch.delenv("IMMICH_API_KEY", raising=False)
    config_path = _write_config_file(
        tmp_path,
        {
            "immich": {
                "url": "https://immich.example.com",
                "accounts": [
                    {"name": "alice", "api_key": "alice-key"},
                    {"name": "bob", "api_key": "bob-key"},
                ],
            }
        },
    )
    monkeypatch.setenv("CONFIG_FILE", str(config_path))

    config = load_config(load_env_file=False)

    assert config.immich_url == "https://immich.example.com"
    assert [a.name for a in config.accounts] == ["alice", "bob"]
    assert [a.api_key for a in config.accounts] == ["alice-key", "bob-key"]
    # Backward-compatible single-account view sees the first configured account.
    assert config.immich_api_key == "alice-key"


def test_config_file_reads_external_url_and_timeout(monkeypatch, tmp_path):
    config_path = _write_config_file(
        tmp_path,
        {
            "immich": {
                "url": "http://immich-server:2283",
                "external_url": "https://immich.example.com",
                "timeout_seconds": 120,
                "accounts": [{"name": "default", "api_key": "secret"}],
            }
        },
    )
    monkeypatch.setenv("CONFIG_FILE", str(config_path))

    config = load_config(load_env_file=False)

    assert config.immich_link_base_url == "https://immich.example.com"
    assert config.immich_timeout_seconds == 120.0


def test_missing_config_file_falls_back_to_legacy_env_vars_with_no_error(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("CONFIG_FILE", str(tmp_path / "does-not-exist.json"))
    monkeypatch.setenv("IMMICH_URL", "https://immich.example.com")
    monkeypatch.setenv("IMMICH_API_KEY", "secret")

    config = load_config(load_env_file=False)

    assert config.immich_url == "https://immich.example.com"
    assert config.immich_api_key == "secret"


def test_config_file_wins_over_legacy_env_vars_and_logs_a_warning(
    monkeypatch, tmp_path, caplog
):
    config_path = _write_config_file(
        tmp_path,
        {
            "immich": {
                "url": "https://from-file.example.com",
                "accounts": [{"name": "default", "api_key": "file-key"}],
            }
        },
    )
    monkeypatch.setenv("CONFIG_FILE", str(config_path))
    monkeypatch.setenv("IMMICH_URL", "https://from-env.example.com")
    monkeypatch.setenv("IMMICH_API_KEY", "env-key")

    with caplog.at_level("WARNING"):
        config = load_config(load_env_file=False)

    assert config.immich_url == "https://from-file.example.com"
    assert config.immich_api_key == "file-key"
    assert "ignored" in caplog.text


def test_malformed_config_file_json_raises_config_error(monkeypatch, tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text("{not valid json")
    monkeypatch.setenv("CONFIG_FILE", str(config_path))

    with pytest.raises(ConfigError, match=str(config_path)):
        load_config(load_env_file=False)


def test_config_file_missing_immich_url_raises_config_error(monkeypatch, tmp_path):
    config_path = _write_config_file(
        tmp_path,
        {"immich": {"accounts": [{"name": "default", "api_key": "secret"}]}},
    )
    monkeypatch.setenv("CONFIG_FILE", str(config_path))

    with pytest.raises(ConfigError, match="immich.url"):
        load_config(load_env_file=False)


def test_config_file_with_zero_accounts_raises_config_error(monkeypatch, tmp_path):
    config_path = _write_config_file(
        tmp_path,
        {"immich": {"url": "https://immich.example.com", "accounts": []}},
    )
    monkeypatch.setenv("CONFIG_FILE", str(config_path))

    with pytest.raises(ConfigError, match="accounts"):
        load_config(load_env_file=False)


def test_config_file_with_duplicate_account_names_raises_config_error(
    monkeypatch, tmp_path
):
    config_path = _write_config_file(
        tmp_path,
        {
            "immich": {
                "url": "https://immich.example.com",
                "accounts": [
                    {"name": "default", "api_key": "one"},
                    {"name": "default", "api_key": "two"},
                ],
            }
        },
    )
    monkeypatch.setenv("CONFIG_FILE", str(config_path))

    with pytest.raises(ConfigError, match="duplicate"):
        load_config(load_env_file=False)


def test_config_file_path_that_is_a_directory_falls_back_to_legacy_env_vars(
    monkeypatch, tmp_path
):
    # A Docker bind mount whose host source doesn't exist yet is auto-created as a directory --
    # this must behave the same as a config file that was never created at all.
    config_dir = tmp_path / "config.json"
    config_dir.mkdir()
    monkeypatch.setenv("CONFIG_FILE", str(config_dir))
    monkeypatch.setenv("IMMICH_URL", "https://immich.example.com")
    monkeypatch.setenv("IMMICH_API_KEY", "secret")

    config = load_config(load_env_file=False)

    assert config.immich_url == "https://immich.example.com"
    assert config.immich_api_key == "secret"
