"""Tests for the /diagnostics endpoint."""

from __future__ import annotations

from immich_dog_tagger.api.dependencies import get_config


def test_diagnostics_endpoint_returns_expected_shape(api_client, monkeypatch, tmp_path):
    from immich_dog_tagger.config import Config

    fake_config = Config(
        immich_url="http://localhost",
        immich_api_key="test",
        state_dir=tmp_path / "state",
        cache_dir=tmp_path / "cache",
        yolo_model=tmp_path / "yolo11n.pt",
        crop_padding=0.1,
    )

    api_client.app.dependency_overrides[get_config] = lambda: fake_config

    response = api_client.get("/diagnostics")
    assert response.status_code == 200

    data = response.json()
    assert "db" in data
    assert "scheduler" in data
    assert "jobs" in data
    assert "backup" in data
    assert "derived_data" in data


def test_diagnostics_backup_section_reports_no_backup_when_empty(
    api_client, monkeypatch, tmp_path
):
    from immich_dog_tagger.config import Config

    fake_config = Config(
        immich_url="http://localhost",
        immich_api_key="test",
        state_dir=tmp_path / "state",
        cache_dir=tmp_path / "cache",
        yolo_model=tmp_path / "yolo11n.pt",
        crop_padding=0.1,
    )
    api_client.app.dependency_overrides[get_config] = lambda: fake_config

    response = api_client.get("/diagnostics")
    data = response.json()
    assert data["backup"]["has_backup"] is False
    assert data["backup"]["last_backup_at"] is None


def test_diagnostics_derived_data_healthy_on_empty_db(
    api_client, monkeypatch, tmp_path
):
    from immich_dog_tagger.config import Config

    fake_config = Config(
        immich_url="http://localhost",
        immich_api_key="test",
        state_dir=tmp_path / "state",
        cache_dir=tmp_path / "cache",
        yolo_model=tmp_path / "yolo11n.pt",
        crop_padding=0.1,
    )
    api_client.app.dependency_overrides[get_config] = lambda: fake_config

    response = api_client.get("/diagnostics")
    data = response.json()
    assert data["derived_data"]["healthy"] is True
    assert data["derived_data"]["total_missing"] == 0
