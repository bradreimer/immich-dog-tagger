from pathlib import Path

from immich_dog_tagger.config import load_config


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
