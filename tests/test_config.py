from pathlib import Path

from immich_dog_tagger.config import load_config


def test_default_configuration(monkeypatch):
    monkeypatch.delenv("IMMICH_URL", raising=False)
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

    config = load_config()

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
    monkeypatch.setenv(
        "STATE_DIR",
        "/state",
    )
    monkeypatch.setenv(
        "CACHE_DIR",
        "/cache",
    )

    config = load_config(load_env_file=False)

    assert config.state_dir == Path("/state")
    assert config.cache_dir == Path("/cache")
    assert config.crop_dir == Path("/cache/crops")
