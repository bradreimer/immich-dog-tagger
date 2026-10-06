from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy.orm import Session

from immich_dog_tagger.config import Config, ImmichAccount
from immich_dog_tagger.services.accounts import AccountService
from immich_dog_tagger.services.job_execution import _scan_handler, _sync_handler

MODULE = "immich_dog_tagger.services.job_execution"


class RecordingProgress:
    def __init__(self, account_id=None):
        self.messages: list[str] = []
        self.job = SimpleNamespace(account_id=account_id)

    def set(self, current=None, total=None, message=None):
        if message is not None:
            self.messages.append(message)

    def message(self, value):
        self.messages.append(value)

    def is_cancel_requested(self) -> bool:
        return False


def _config(tmp_path: Path, *, names: tuple[str, ...]) -> Config:
    if not names:
        # Legacy install: only IMMICH_API_KEY, no declared accounts.
        return Config(
            immich_url="http://fake",
            immich_api_key="legacy-key",
            state_dir=tmp_path,
            cache_dir=tmp_path,
            yolo_model=tmp_path / "unused.pt",
            crop_padding=0.0,
        )

    return Config(
        immich_url="http://fake",
        immich_api_key="",
        state_dir=tmp_path,
        cache_dir=tmp_path,
        yolo_model=tmp_path / "unused.pt",
        crop_padding=0.0,
        accounts=tuple(ImmichAccount(name=n, api_key=f"key-{n}") for n in names),
    )


def _install_fakes(monkeypatch, fail_for: int | None = None):
    """Record which account each Scanner/SyncService is built and run for."""
    scanned: list[int] = []
    synced: list[int] = []

    class FakeScanner:
        def __init__(self, client, session, cache_dir=None, account_id=None):
            self.account_id = account_id

        def scan(self, limit=None, force=False, should_cancel=None):
            if fail_for is not None and self.account_id == fail_for:
                raise RuntimeError("bad api key")

            scanned.append(self.account_id)
            return 2

    class FakeSyncService:
        def __init__(self, session, albums, policy=None, tags=None, account_id=None):
            self.account_id = account_id

        def sync(self, dry_run=False):
            if fail_for is not None and self.account_id == fail_for:
                raise RuntimeError("bad api key")

            synced.append(self.account_id)
            return SimpleNamespace(
                identities=[SimpleNamespace(identity="Rex", assets=3)],
                skipped_low_confidence=0,
                skipped_unknown=0,
                skipped_missing_asset=0,
                failed_identities=[],
            )

    monkeypatch.setattr(f"{MODULE}.Scanner", FakeScanner)
    monkeypatch.setattr(f"{MODULE}.SyncService", FakeSyncService)
    monkeypatch.setattr(f"{MODULE}._create_client", lambda config, account: object())
    monkeypatch.setattr(f"{MODULE}.AlbumService", lambda client: object())
    monkeypatch.setattr(f"{MODULE}.TagService", lambda client: object())

    return scanned, synced


def _ids(session, config) -> dict[str, int]:
    service = AccountService(session)
    service.sync_from_config(config)
    return {a.name: a.id for a in service.list_accounts()}


@pytest.mark.parametrize("handler_factory", [_scan_handler, _sync_handler])
def test_handler_runs_every_account_when_job_has_none(
    engine, tmp_path, monkeypatch, handler_factory
):
    scanned, synced = _install_fakes(monkeypatch)
    config = _config(tmp_path, names=("alice", "bob"))

    with Session(engine) as session:
        ids = _ids(session, config)
        result = handler_factory(session, config, {})(RecordingProgress())

    assert sorted(scanned or synced) == sorted(ids.values())
    assert result["failed_accounts"] == 0


@pytest.mark.parametrize("handler_factory", [_scan_handler, _sync_handler])
def test_handler_explicit_account_runs_only_that_account(
    engine, tmp_path, monkeypatch, handler_factory
):
    scanned, synced = _install_fakes(monkeypatch)
    config = _config(tmp_path, names=("alice", "bob"))

    with Session(engine) as session:
        ids = _ids(session, config)
        result = handler_factory(session, config, {})(RecordingProgress(ids["bob"]))

    assert (scanned or synced) == [ids["bob"]]
    assert "failed_accounts" not in result


@pytest.mark.parametrize("handler_factory", [_scan_handler, _sync_handler])
def test_handler_isolates_a_failing_account(
    engine, tmp_path, monkeypatch, handler_factory
):
    config = _config(tmp_path, names=("alice", "bob"))

    with Session(engine) as session:
        ids = _ids(session, config)
        scanned, synced = _install_fakes(monkeypatch, fail_for=ids["alice"])
        progress = RecordingProgress()

        result = handler_factory(session, config, {})(progress)

    assert (scanned or synced) == [ids["bob"]]
    assert result["failed_accounts"] == 1
    assert any("[alice] failed: bad api key" in m for m in progress.messages)


@pytest.mark.parametrize("handler_factory", [_scan_handler, _sync_handler])
def test_handler_fails_when_every_account_fails(
    engine, tmp_path, monkeypatch, handler_factory
):
    config = _config(tmp_path, names=("alice", "bob"))

    with Session(engine) as session:
        ids = _ids(session, config)
        _install_fakes(monkeypatch, fail_for=ids["alice"])

        class AlwaysFails:
            def __init__(self, *a, **k):
                pass

            def scan(self, **k):
                raise RuntimeError("bad api key")

            def sync(self, **k):
                raise RuntimeError("bad api key")

        monkeypatch.setattr(f"{MODULE}.Scanner", AlwaysFails)
        monkeypatch.setattr(f"{MODULE}.SyncService", AlwaysFails)

        with pytest.raises(RuntimeError, match="failed for every account"):
            handler_factory(session, config, {})(RecordingProgress())


@pytest.mark.parametrize("handler_factory", [_scan_handler, _sync_handler])
def test_handler_single_and_legacy_config_unchanged(
    engine, tmp_path, monkeypatch, handler_factory
):
    scanned, synced = _install_fakes(monkeypatch)

    with Session(engine) as session:
        result = handler_factory(session, _config(tmp_path, names=()), {})(
            RecordingProgress()
        )

    assert len(scanned or synced) == 1
    assert "failed_accounts" not in result
