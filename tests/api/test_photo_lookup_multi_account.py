"""
Photo Lookup's per-photo requests (image, Repair) use the API key of the account that owns
the photo, not always the default account's (multi-account spec FR-7).
"""

import io
from datetime import UTC, datetime
from pathlib import Path

import pytest
from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session

from immich_dog_tagger.api import dependencies
from immich_dog_tagger.api.dependencies import get_config
from immich_dog_tagger.config import Config, ImmichAccount
from immich_dog_tagger.immich import ImmichGetAssetError
from immich_dog_tagger.models import Asset
from immich_dog_tagger.services.accounts import (
    AccountResolutionError,
    AccountService,
    resolve_asset_account,
)


def _config(tmp_path: Path, names=("A", "B")) -> Config:
    return Config(
        immich_url="http://fake",
        immich_api_key="",
        state_dir=tmp_path,
        cache_dir=tmp_path,
        yolo_model=tmp_path / "unused.pt",
        crop_padding=0.0,
        accounts=tuple(ImmichAccount(name=n, api_key=f"key-{n}") for n in names),
    )


class KeyedClient:
    """Stands in for an ImmichClient; refuses assets its key doesn't own."""

    def __init__(self, api_key: str, owned: set[str]):
        self.api_key = api_key
        self.owned = owned
        self.downloads: list[str] = []
        self.get_asset_calls: list[str] = []

    def download_asset(self, asset_id: str) -> bytes:
        self.downloads.append(asset_id)

        if asset_id not in self.owned:
            raise AssertionError(f"{self.api_key} cannot read {asset_id}")

        buffer = io.BytesIO()
        Image.new("RGB", (200, 100), "white").save(buffer, format="JPEG")

        return buffer.getvalue()

    def get_asset(self, asset_id: str):
        self.get_asset_calls.append(asset_id)
        raise ImmichGetAssetError("stop after metadata fetch")


@pytest.fixture
def accounts(api_client, engine, tmp_path):
    config = _config(tmp_path)

    with Session(engine) as session:
        by_name = {
            a.name: a.id for a in AccountService(session).sync_from_config(config)
        }

        for immich_id, name in (("asset-a", "A"), ("asset-b", "B")):
            session.add(
                Asset(
                    immich_asset_id=immich_id,
                    extension=".jpg",
                    captured_at=datetime(2020, 6, 1, tzinfo=UTC),
                    account_id=by_name[name],
                )
            )

        session.add(
            Asset(
                immich_asset_id="asset-legacy",
                extension=".jpg",
                captured_at=datetime(2020, 6, 1, tzinfo=UTC),
            )
        )
        session.commit()

    clients = {
        "key-A": KeyedClient("key-A", {"asset-a", "asset-legacy"}),
        "key-B": KeyedClient("key-B", {"asset-b"}),
    }
    api_client.app.dependency_overrides[get_config] = lambda: config
    api_client.app.dependency_overrides[dependencies.get_immich_client] = lambda: (
        clients["key-A"]
    )
    dependencies._account_client.cache_clear()
    # The non-default account's client is built per key; hand back the fakes.
    original = dependencies._account_client
    dependencies._account_client = lambda url, key, timeout: clients[key]

    yield api_client, clients, config

    dependencies._account_client = original


def test_image_for_a_non_default_account_uses_its_own_key(accounts):
    api_client, clients, _ = accounts

    response = api_client.get("/photo-lookup/asset-b/image")

    assert response.status_code == 200
    assert clients["key-B"].downloads == ["asset-b"]
    assert clients["key-A"].downloads == []


def test_image_for_the_default_account_is_unchanged(accounts):
    api_client, clients, _ = accounts

    assert api_client.get("/photo-lookup/asset-a/image").status_code == 200
    assert clients["key-A"].downloads == ["asset-a"]


def test_image_for_an_asset_with_no_account_uses_the_default_key(accounts):
    api_client, clients, _ = accounts

    assert api_client.get("/photo-lookup/asset-legacy/image").status_code == 200
    assert clients["key-A"].downloads == ["asset-legacy"]


def test_repair_for_a_non_default_account_uses_its_own_key(accounts):
    api_client, clients, _ = accounts

    response = api_client.post("/photo-lookup/asset-b/repair")

    assert response.status_code == 200
    assert clients["key-B"].get_asset_calls == ["asset-b"]
    assert clients["key-A"].get_asset_calls == []
    assert "another Immich account" not in response.json()["message"]


def test_removed_account_gives_an_actionable_error(accounts, api_client, tmp_path):
    api_client.app.dependency_overrides[get_config] = lambda: _config(tmp_path, ("A",))

    response = api_client.get("/photo-lookup/asset-b/image")

    assert response.status_code == 409
    assert "'B'" in response.json()["detail"]


def test_resolve_asset_account(accounts, engine):
    _, _, config = accounts

    with Session(engine) as session:
        assert resolve_asset_account(session, config, "asset-b").api_key == "key-B"
        assert resolve_asset_account(session, config, "asset-a").api_key == "key-A"
        # Unscanned or account-less photos fall back to the default account.
        assert resolve_asset_account(session, config, "asset-legacy").api_key == "key-A"
        assert resolve_asset_account(session, config, "nope").api_key == "key-A"

        session.execute(select(Asset))  # session still usable

    with Session(engine) as session, pytest.raises(AccountResolutionError):
        resolve_asset_account(session, _config(Path("."), ("A",)), "asset-b")
