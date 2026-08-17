"""Tests for the /settings endpoint."""

from __future__ import annotations

from sqlalchemy.orm import Session

from immich_dog_tagger.api.dependencies import get_config
from immich_dog_tagger.config import Config
from immich_dog_tagger.models import Asset
from immich_dog_tagger.version import get_version


def _fake_config(tmp_path, immich_url: str) -> Config:
    return Config(
        immich_url=immich_url,
        immich_api_key="super-secret-key",
        state_dir=tmp_path / "state",
        cache_dir=tmp_path / "cache",
        yolo_model=tmp_path / "yolo11n.pt",
        crop_padding=0.1,
    )


def test_settings_returns_immich_url_and_scanned_count(api_client, tmp_path, engine):
    fake_config = _fake_config(tmp_path, "http://localhost:2283")
    api_client.app.dependency_overrides[get_config] = lambda: fake_config

    with Session(engine) as session:
        session.add_all(
            [
                Asset(immich_asset_id="asset-1", extension="jpg"),
                Asset(immich_asset_id="asset-2", extension="jpg"),
            ]
        )
        session.commit()

    response = api_client.get("/settings")
    assert response.status_code == 200

    data = response.json()
    assert data["immich_url"] == "http://localhost:2283"
    assert data["scanned_image_count"] == 2


def test_settings_returns_zero_count_when_no_assets_scanned(api_client, tmp_path):
    fake_config = _fake_config(tmp_path, "http://localhost:2283")
    api_client.app.dependency_overrides[get_config] = lambda: fake_config

    response = api_client.get("/settings")
    assert response.status_code == 200

    data = response.json()
    assert data["scanned_image_count"] == 0


def test_settings_never_returns_api_key(api_client, tmp_path):
    fake_config = _fake_config(tmp_path, "http://localhost:2283")
    api_client.app.dependency_overrides[get_config] = lambda: fake_config

    response = api_client.get("/settings")
    assert response.status_code == 200
    assert "super-secret-key" not in response.text
    assert "immich_api_key" not in response.json()


def test_settings_returns_app_version(api_client, tmp_path):
    fake_config = _fake_config(tmp_path, "http://localhost:2283")
    api_client.app.dependency_overrides[get_config] = lambda: fake_config

    response = api_client.get("/settings")
    assert response.status_code == 200
    assert response.json()["version"] == get_version()
