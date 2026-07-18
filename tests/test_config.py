from pathlib import Path

from immich_dog_tagger.config import load_config


def test_default_configuration(monkeypatch):
    monkeypatch.delenv("IMMICH_URL", raising=False)
    monkeypatch.delenv("IMMICH_API_KEY", raising=False)
    monkeypatch.delenv("DATA_DIR", raising=False)

    config = load_config()

    assert config.immich_url == ""
    assert config.immich_api_key == ""
    assert config.data_dir == Path("./data")


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
        "DATA_DIR",
        "/tmp/state",
    )

    config = load_config()

    assert config.immich_url == "https://immich.example.com"
    assert config.immich_api_key == "secret"
    assert config.data_dir == Path("/tmp/state")