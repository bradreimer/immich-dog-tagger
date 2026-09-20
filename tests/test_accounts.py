import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from immich_dog_tagger.config import Config
from immich_dog_tagger.config import ImmichAccount as ConfiguredAccount
from immich_dog_tagger.models import Asset
from immich_dog_tagger.services.accounts import (
    AccountResolutionError,
    AccountService,
    build_immich_client,
    resolve_account,
)


def _config(tmp_path, accounts=(), immich_api_key="") -> Config:
    return Config(
        immich_url="http://immich.example.com",
        immich_api_key=immich_api_key,
        state_dir=tmp_path,
        cache_dir=tmp_path,
        yolo_model=tmp_path / "model.pt",
        crop_padding=0.15,
        accounts=accounts,
    )


def test_sync_from_config_creates_a_row_per_account_plus_default(engine, tmp_path):
    config = _config(
        tmp_path,
        accounts=(
            ConfiguredAccount(name="alice", api_key="alice-key"),
            ConfiguredAccount(name="bob", api_key="bob-key"),
        ),
    )

    with Session(engine) as session:
        accounts = AccountService(session).sync_from_config(config)
        assert sorted(a.name for a in accounts) == ["alice", "bob", "default"]


def test_sync_from_config_backfills_pre_existing_assets_onto_default(engine, tmp_path):
    with Session(engine) as session:
        session.add(Asset(immich_asset_id="legacy", extension=".jpg"))
        session.commit()

    config = _config(tmp_path, accounts=(ConfiguredAccount(name="alice", api_key="k"),))

    with Session(engine) as session:
        AccountService(session).sync_from_config(config)

        default_account = AccountService(session).get_by_name("default")
        legacy_asset = session.scalar(
            select(Asset).where(Asset.immich_asset_id == "legacy")
        )

        assert legacy_asset.account_id == default_account.id


def test_sync_from_config_is_idempotent(engine, tmp_path):
    config = _config(tmp_path, accounts=(ConfiguredAccount(name="alice", api_key="k"),))

    with Session(engine) as session:
        first = AccountService(session).sync_from_config(config)
        second = AccountService(session).sync_from_config(config)

        assert len(first) == len(second) == 2  # alice + default


def test_sync_from_config_never_deletes_an_orphaned_account(engine, tmp_path):
    config_with_bob = _config(
        tmp_path, accounts=(ConfiguredAccount(name="bob", api_key="k"),)
    )

    with Session(engine) as session:
        AccountService(session).sync_from_config(config_with_bob)

    config_without_bob = _config(
        tmp_path, accounts=(ConfiguredAccount(name="alice", api_key="k"),)
    )

    with Session(engine) as session:
        AccountService(session).sync_from_config(config_without_bob)

        names = {a.name for a in AccountService(session).list_accounts()}
        assert "bob" in names  # left in place, not deleted


def test_resolve_account_by_explicit_id(engine, tmp_path):
    config = _config(
        tmp_path, accounts=(ConfiguredAccount(name="alice", api_key="alice-key"),)
    )

    with Session(engine) as session:
        AccountService(session).sync_from_config(config)
        alice = AccountService(session).get_by_name("alice")

        resolved = resolve_account(session, config, alice.id)

    assert resolved.name == "alice"
    assert resolved.api_key == "alice-key"


def test_resolve_account_none_falls_back_to_first_configured_account(engine, tmp_path):
    config = _config(
        tmp_path,
        accounts=(
            ConfiguredAccount(name="alice", api_key="alice-key"),
            ConfiguredAccount(name="bob", api_key="bob-key"),
        ),
    )

    with Session(engine) as session:
        resolved = resolve_account(session, config, None)

    assert resolved.name == "alice"
    assert resolved.api_key == "alice-key"


def test_resolve_account_none_falls_back_to_legacy_immich_api_key(engine, tmp_path):
    """
    Backward compatibility (issue #346/#348): a Config built directly with
    just immich_api_key set (accounts left at its empty-tuple default) --
    the pattern this project's existing tests already use everywhere --
    must resolve exactly like the pre-#346 single-client behavior, with no
    account row required in state.db at all.
    """
    config = _config(tmp_path, immich_api_key="legacy-key")

    with Session(engine) as session:
        resolved = resolve_account(session, config, None)

    assert resolved.api_key == "legacy-key"
    assert resolved.id is None


def test_resolve_account_none_resolves_to_an_empty_key_when_nothing_is_configured(
    engine, tmp_path
):
    """
    Backward compatibility: this must never raise, even with nothing
    configured at all -- several existing tests deliberately run a pipeline
    stage against a faked-out Immich client with no credentials set, and
    raising here would break that pattern for no benefit (nothing
    downstream would make a real network call either way).
    """
    config = _config(tmp_path)

    with Session(engine) as session:
        resolved = resolve_account(session, config, None)

    assert resolved.api_key == ""


def test_resolve_account_raises_for_an_unknown_id(engine, tmp_path):
    config = _config(tmp_path, accounts=(ConfiguredAccount(name="alice", api_key="k"),))

    with Session(engine) as session, pytest.raises(AccountResolutionError):
        resolve_account(session, config, 999999)


def test_resolve_account_raises_for_an_orphaned_account(engine, tmp_path):
    """A DB account row whose name is no longer in Config.accounts (renamed
    or removed there) must be surfaced as an error, not silently resolved
    against a stale/wrong key."""
    config_with_bob = _config(
        tmp_path, accounts=(ConfiguredAccount(name="bob", api_key="k"),)
    )

    with Session(engine) as session:
        AccountService(session).sync_from_config(config_with_bob)
        bob = AccountService(session).get_by_name("bob")

    config_without_bob = _config(
        tmp_path, accounts=(ConfiguredAccount(name="alice", api_key="k"),)
    )

    with Session(engine) as session, pytest.raises(AccountResolutionError):
        resolve_account(session, config_without_bob, bob.id)


def test_build_immich_client_uses_the_resolved_accounts_key(tmp_path):
    from immich_dog_tagger.services.accounts import ResolvedAccount

    config = _config(tmp_path)
    resolved = ResolvedAccount(id=1, name="alice", api_key="alice-key")

    client = build_immich_client(config, resolved)

    assert client.url == config.immich_url
    assert client.client.headers["x-api-key"] == "alice-key"
