"""
Issues #432/#434: photos from an account removed from configuration (or set to
`"enabled": false`) stay visible in Settings, Library and Metrics (state.db is
the source of truth) but leave every pending-review surface.
"""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from immich_dog_tagger.api.dependencies import get_config
from immich_dog_tagger.config import Config, ImmichAccount
from immich_dog_tagger.enums import Species
from immich_dog_tagger.models import Asset, Crop, CropClassification, Detection
from immich_dog_tagger.services.accounts import AccountService


def _config(
    tmp_path: Path, names: tuple[str, ...], disabled: tuple[str, ...] = ()
) -> Config:
    return Config(
        immich_url="http://fake",
        immich_api_key="",
        state_dir=tmp_path,
        cache_dir=tmp_path,
        yolo_model=tmp_path / "unused.pt",
        crop_padding=0.0,
        accounts=tuple(
            ImmichAccount(name=n, api_key=f"key-{n}", enabled=n not in disabled)
            for n in names
        ),
    )


def _add_unreviewed_photo(session: Session, immich_id: str, account_id: int) -> None:
    asset = Asset(
        immich_asset_id=immich_id,
        extension=".jpg",
        captured_at=datetime(2020, 6, 1, tzinfo=UTC),
        account_id=account_id,
    )
    session.add(asset)
    session.flush()

    detection = Detection(
        asset_id=asset.id, label="dog", confidence=0.9, x1=0, y1=0, x2=1, y2=1
    )
    session.add(detection)
    session.flush()

    crop = Crop(detection_id=detection.id, path=f"{immich_id}.jpg", species=Species.DOG)
    session.add(crop)
    session.flush()

    session.add(CropClassification(crop=crop, identity=None, confidence=0.1))
    session.commit()


@pytest.fixture(params=["removed", "disabled"])
def removed_account(request, api_client, engine, tmp_path):
    """Accounts A and B scanned; then B is removed from, or disabled in, the config."""
    with Session(engine) as session:
        by_name = {
            a.name: a.id
            for a in AccountService(session).sync_from_config(
                _config(tmp_path, ("A", "B"))
            )
        }
        _add_unreviewed_photo(session, "asset-a", by_name["A"])
        _add_unreviewed_photo(session, "asset-b", by_name["B"])

    if request.param == "removed":
        config = _config(tmp_path, ("A",))
    else:
        config = _config(tmp_path, ("A", "B"), disabled=("B",))

    # Startup sync, as the app does when it loads the edited configuration.
    with Session(engine) as session:
        AccountService(session).sync_from_config(config)

    api_client.app.dependency_overrides[get_config] = lambda: config

    return api_client, by_name


def test_settings_marks_the_account_inactive(removed_account):
    api_client, _ = removed_account

    accounts = api_client.get("/settings").json()["accounts"]

    assert {a["name"]: a["active"] for a in accounts} == {"A": True, "B": False}


def test_accounts_endpoint_marks_the_account_inactive(removed_account):
    api_client, _ = removed_account

    accounts = api_client.get("/accounts").json()

    assert {a["name"]: a["active"] for a in accounts} == {"A": True, "B": False}


def test_review_queue_only_offers_active_accounts_photos(removed_account):
    api_client, by_name = removed_account

    everything = api_client.get("/review").json()
    only_inactive = api_client.get(
        "/review", params={"account_id": by_name["B"]}
    ).json()

    assert [item["account"] for item in everything] == ["A"]
    assert only_inactive == []


def test_review_queue_stats_ignore_the_inactive_accounts_photos(removed_account):
    api_client, _ = removed_account

    assert api_client.get("/review/stats").json()["remaining"] == 1


def test_library_still_includes_the_removed_accounts_photos(removed_account):
    api_client, by_name = removed_account

    everything = api_client.get("/library").json()
    only_removed = api_client.get(
        "/library", params={"account_id": by_name["B"]}
    ).json()

    assert everything["total"] == 2
    assert only_removed["total"] == 1


def test_metrics_still_count_the_removed_accounts_photos_by_name(removed_account):
    api_client, _ = removed_account

    libraries = api_client.get("/metrics/pets-per-library").json()["libraries"]

    assert {item["library"]: item["dogs_detected"] for item in libraries} == {
        "A": 1,
        "B": 1,
    }


def test_reactivating_the_account_restores_its_photos_in_review(
    removed_account, engine, tmp_path
):
    api_client, _ = removed_account
    config = _config(tmp_path, ("A", "B"))

    with Session(engine) as session:
        AccountService(session).sync_from_config(config)

    api_client.app.dependency_overrides[get_config] = lambda: config

    assert {item["account"] for item in api_client.get("/review").json()} == {"A", "B"}


def test_settings_distinguishes_removed_from_disabled(api_client, engine, tmp_path):
    with Session(engine) as session:
        AccountService(session).sync_from_config(_config(tmp_path, ("A", "B", "C")))

    config = _config(tmp_path, ("A", "B"), disabled=("B",))
    api_client.app.dependency_overrides[get_config] = lambda: config

    accounts = api_client.get("/settings").json()["accounts"]

    assert {a["name"]: (a["configured"], a["active"]) for a in accounts} == {
        "A": (True, True),
        "B": (True, False),
        "C": (False, False),
    }
