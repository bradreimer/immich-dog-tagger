import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from immich_dog_tagger.enums import AssetStatus
from immich_dog_tagger.immich import (
    ImmichAssetNotFoundError,
    ImmichGetAssetError,
    ImmichTagAssetsError,
)
from immich_dog_tagger.models import (
    Asset,
    Crop,
    CropClassification,
    Detection,
    SyncedAsset,
)
from immich_dog_tagger.services.sync import SyncService
from immich_dog_tagger.services.sync_audit import SyncAuditService
from immich_dog_tagger.services.sync_policy import SyncPolicy


class FakeMembership:
    """Stands in for AlbumService/TagService: `members` maps (species, identity) -> set of
    asset ids, or is absent when the album/tag doesn't exist."""

    def __init__(self, members=None, fail_add=False):
        self.members = {k: set(v) for k, v in (members or {}).items()}
        self.fail_add = fail_add

    def member_ids(self, identity, species="dog"):
        members = self.members.get((species, identity))
        return None if members is None else set(members)

    def sync_identity(self, identity, asset_ids, species="dog"):
        if self.fail_add:
            raise ImmichTagAssetsError(
                "rejected",
                failures=[{"id": "x", "success": False, "error": "no_permission"}],
            )
        self.members.setdefault((species, identity), set()).update(asset_ids)

    def remove_from_identity(self, identity, asset_ids, species="dog"):
        if (species, identity) in self.members:
            self.members[(species, identity)] -= set(asset_ids)


def _classify(session, immich_id, identity, species="dog", account_id=None):
    asset = Asset(
        immich_asset_id=immich_id,
        checksum=immich_id,
        extension=".jpg",
        account_id=account_id,
    )
    detection = Detection(
        asset=asset, label=species, confidence=1.0, x1=0, y1=0, x2=10, y2=10
    )
    crop = Crop(detection=detection, path=f"{immich_id}.jpg", species=species)
    session.add(CropClassification(crop=crop, identity=identity, confidence=0.95))
    session.commit()


def _audit(session, albums, tags, **policy):
    return SyncAuditService(
        SyncService(session, albums, policy=SyncPolicy(**policy), tags=tags)
    )


def test_audit_reports_album_members_missing_the_tag(engine):
    with Session(engine) as session:
        _classify(session, "a1", "Fibs")
        _classify(session, "a2", "Fibs")
        albums = FakeMembership({("dog", "Fibs"): {"a1", "a2"}})
        tags = FakeMembership({("dog", "Fibs"): {"a1"}})

        report = _audit(session, albums, tags).audit()

        assert not report.clean
        assert report.drifts[0].missing_tag == ["a2"]
        assert report.missing_tag == 1
        assert report.missing_from_album == 0


def test_audit_reports_a_missing_tag_entirely(engine):
    with Session(engine) as session:
        _classify(session, "a1", "Fibs")
        albums = FakeMembership({("dog", "Fibs"): {"a1"}})

        report = _audit(session, albums, FakeMembership()).audit()

        assert report.drifts[0].missing_tag == ["a1"]


def test_audit_is_clean_when_immich_matches(engine):
    with Session(engine) as session:
        _classify(session, "a1", "Fibs")
        both = {("dog", "Fibs"): {"a1"}}

        report = _audit(session, FakeMembership(both), FakeMembership(both)).audit()

        assert report.clean
        assert report.checked == 1


def test_audit_ignores_a_missing_album_below_the_album_threshold(engine):
    with Session(engine) as session:
        _classify(session, "a1", "Fibs")
        tags = FakeMembership({("dog", "Fibs"): {"a1"}})

        report = _audit(
            session, FakeMembership(), tags, album_minimum_assets=50
        ).audit()

        assert report.clean


def test_audit_reports_a_missing_album_at_or_above_the_threshold(engine):
    with Session(engine) as session:
        _classify(session, "a1", "Fibs")
        tags = FakeMembership({("dog", "Fibs"): {"a1"}})

        report = _audit(session, FakeMembership(), tags, album_minimum_assets=1).audit()

        assert report.drifts[0].missing_from_album == ["a1"]


def test_audit_reports_extras_no_longer_assigned_to_the_identity(engine):
    with Session(engine) as session:
        _classify(session, "a1", "Fibs")
        both = {("dog", "Fibs"): {"a1", "stale"}}

        report = _audit(session, FakeMembership(both), FakeMembership(both)).audit()

        assert report.drifts[0].extra_in_tag == ["stale"]
        assert report.drifts[0].extra_in_album == ["stale"]
        assert report.extras == 2


def test_audit_never_writes(engine):
    with Session(engine) as session:
        _classify(session, "a1", "Fibs")
        albums = FakeMembership({("dog", "Fibs"): {"a1"}})
        tags = FakeMembership({("dog", "Fibs"): set()})

        _audit(session, albums, tags).audit()

        assert tags.members[("dog", "Fibs")] == set()
        assert session.scalars(select(SyncedAsset)).all() == []


def test_audit_isolates_an_identity_whose_read_fails(engine):
    class Exploding(FakeMembership):
        def member_ids(self, identity, species="dog"):
            if identity == "Fibs":
                raise TimeoutError("boom")
            return super().member_ids(identity, species)

    with Session(engine) as session:
        _classify(session, "a1", "Fibs")
        _classify(session, "a2", "Henri")

        report = _audit(session, FakeMembership(), Exploding()).audit()

        assert [f.identity for f in report.failures] == ["Fibs"]
        assert [d.identity for d in report.drifts] == ["Henri"]
        assert not report.clean


def test_repair_adds_missing_tags_and_removes_extras_then_is_idempotent(engine):
    with Session(engine) as session:
        _classify(session, "a1", "Fibs")
        _classify(session, "a2", "Fibs")
        albums = FakeMembership({("dog", "Fibs"): {"a1", "a2", "stale"}})
        tags = FakeMembership({("dog", "Fibs"): {"a1", "stale"}})
        service = _audit(session, albums, tags)

        result = service.repair()

        assert result.added_tags == 1
        assert result.removed == 2
        assert tags.members[("dog", "Fibs")] == {"a1", "a2"}
        assert albums.members[("dog", "Fibs")] == {"a1", "a2"}
        assert not result.failures

        again = service.repair()
        assert again.report.clean
        assert (again.added_tags, again.added_to_albums, again.removed) == (0, 0, 0)


def test_repair_no_prune_leaves_extras(engine):
    with Session(engine) as session:
        _classify(session, "a1", "Fibs")
        both = {("dog", "Fibs"): {"a1", "stale"}}
        albums, tags = FakeMembership(both), FakeMembership(both)

        result = _audit(session, albums, tags).repair(prune=False)

        assert result.removed == 0
        assert tags.members[("dog", "Fibs")] == {"a1", "stale"}


def test_repair_rebuilds_synced_state_from_state_db(engine):
    with Session(engine) as session:
        _classify(session, "a1", "Fibs")
        session.add(SyncedAsset(species="dog", identity="Gone", immich_asset_id="old"))
        session.commit()
        both = {("dog", "Fibs"): {"a1"}, ("dog", "Gone"): {"old"}}

        _audit(session, FakeMembership(both), FakeMembership(both)).repair()

        rows = {
            (r.species, r.identity, r.immich_asset_id)
            for r in session.scalars(select(SyncedAsset))
        }
        assert rows == {("dog", "Fibs", "a1")}


def test_repair_reports_and_retains_state_for_a_failed_identity(engine):
    with Session(engine) as session:
        _classify(session, "a1", "Fibs")
        session.add(SyncedAsset(species="dog", identity="Fibs", immich_asset_id="a1"))
        session.commit()
        albums = FakeMembership({("dog", "Fibs"): {"a1"}})
        tags = FakeMembership({("dog", "Fibs"): set()}, fail_add=True)

        result = _audit(session, albums, tags).repair()

        assert [f.identity for f in result.failures] == ["Fibs"]
        assert result.failures[0].permission_error is True
        rows = session.scalars(select(SyncedAsset)).all()
        assert [r.immich_asset_id for r in rows] == ["a1"]


@pytest.mark.parametrize("prune", [True, False])
def test_repair_clean_library_changes_nothing(engine, prune):
    with Session(engine) as session:
        _classify(session, "a1", "Fibs")
        both = {("dog", "Fibs"): {"a1"}}

        result = _audit(session, FakeMembership(both), FakeMembership(both)).repair(
            prune=prune
        )

        assert result.report.clean
        assert result.removed == 0


class RejectingTags(FakeMembership):
    """Rejects `rejected` ids with no_permission, but still writes the rest."""

    def __init__(self, rejected, error="no_permission"):
        super().__init__()
        self.rejected = set(rejected)
        self.error = error

    def sync_identity(self, identity, asset_ids, species="dog"):
        ok = [a for a in asset_ids if a not in self.rejected]
        self.members.setdefault((species, identity), set()).update(ok)
        bad = [a for a in asset_ids if a in self.rejected]

        if bad:
            raise ImmichTagAssetsError(
                "rejected",
                failures=[
                    {"id": a, "success": False, "error": self.error} for a in bad
                ],
            )


class FakeClient:
    def __init__(self, gone=(), error=None):
        self.gone = set(gone)
        self.error = error

    def get_asset(self, immich_asset_id):
        if self.error is not None:
            raise self.error

        if immich_asset_id in self.gone:
            raise ImmichAssetNotFoundError("Not found or no asset.read access")

        return object()


def _repair_with(session, tags, client):
    return SyncAuditService(
        SyncService(
            session,
            FakeMembership(),
            policy=SyncPolicy(album_minimum_assets=999),
            tags=tags,
        ),
        client=client,
    ).repair()


def test_repair_retires_photos_immich_no_longer_has(engine):
    with Session(engine) as session:
        _classify(session, "a1", "Fibs")
        _classify(session, "gone", "Fibs")

        result = _repair_with(
            session, RejectingTags({"gone"}), FakeClient(gone={"gone"})
        )

        assert result.failures == []
        assert result.retired == 1
        gone = session.scalar(select(Asset).where(Asset.immich_asset_id == "gone"))
        assert gone.status == AssetStatus.REMOVED
        assert not session.scalars(
            select(SyncedAsset).where(SyncedAsset.immich_asset_id == "gone")
        ).all()


def test_repair_keeps_the_failure_when_the_photo_still_exists(engine):
    with Session(engine) as session:
        _classify(session, "locked", "Fibs")

        result = _repair_with(session, RejectingTags({"locked"}), FakeClient())

        assert result.retired == 0
        assert result.failures[0].permission_error
        locked = session.scalar(select(Asset).where(Asset.immich_asset_id == "locked"))
        assert locked.status != AssetStatus.REMOVED


def test_repair_does_not_retire_when_immich_cannot_be_asked(engine):
    with Session(engine) as session:
        _classify(session, "a1", "Fibs")

        result = _repair_with(
            session,
            RejectingTags({"a1"}),
            FakeClient(error=ImmichGetAssetError("503")),
        )

        assert result.retired == 0
        assert result.failures
