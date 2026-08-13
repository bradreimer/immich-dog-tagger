from sqlalchemy.orm import Session

from immich_dog_tagger.models import (
    Asset,
    Crop,
    CropClassification,
    Detection,
    SyncedAsset,
)
from immich_dog_tagger.services.sync import SyncService
from immich_dog_tagger.services.sync_policy import SyncPolicy


class FakeAlbums:
    def __init__(self):
        self.calls = []
        self.removals = []

    def sync_identity(
        self,
        identity,
        asset_ids,
        species="dog",
    ):
        self.calls.append(
            (
                identity,
                asset_ids,
                species,
            )
        )

    def remove_from_identity(
        self,
        identity,
        asset_ids,
        species="dog",
    ):
        self.removals.append(
            (
                identity,
                asset_ids,
                species,
            )
        )


def test_sync_groups_assets(engine):
    with Session(engine) as session:
        asset = Asset(
            immich_asset_id="asset1",
            checksum="abc",
            extension=".jpg",
        )

        detection = Detection(
            asset=asset,
            label="dog",
            confidence=1.0,
            x1=0,
            y1=0,
            x2=10,
            y2=10,
        )

        crop = Crop(
            detection=detection,
            path="crop.jpg",
        )

        classification = CropClassification(
            crop=crop,
            identity="Hermann",
            confidence=0.95,
        )

        session.add(classification)
        session.commit()

        albums = FakeAlbums()

        summary = SyncService(
            session,
            albums,
        ).sync()

        assert summary.identities[0].identity == "Hermann"
        assert summary.identities[0].assets == 1

        assert albums.calls == [
            (
                "Hermann",
                ["asset1"],
                "dog",
            )
        ]


def test_sync_keeps_same_named_dog_and_cat_separate(engine):
    # Regression test (DT-1110): before species-scoping, this aggregation
    # was keyed by identity name alone, so a dog "Max" and a cat "Max"
    # would silently merge into one album with both species' assets.
    with Session(engine) as session:
        dog_asset = Asset(immich_asset_id="dog-asset", checksum="a", extension=".jpg")
        cat_asset = Asset(immich_asset_id="cat-asset", checksum="b", extension=".jpg")

        dog_detection = Detection(
            asset=dog_asset, label="dog", confidence=1.0, x1=0, y1=0, x2=10, y2=10
        )
        cat_detection = Detection(
            asset=cat_asset, label="cat", confidence=1.0, x1=0, y1=0, x2=10, y2=10
        )

        dog_crop = Crop(detection=dog_detection, path="dog.jpg", species="dog")
        cat_crop = Crop(detection=cat_detection, path="cat.jpg", species="cat")

        session.add(CropClassification(crop=dog_crop, identity="Max", confidence=0.95))
        session.add(CropClassification(crop=cat_crop, identity="Max", confidence=0.95))
        session.commit()

        albums = FakeAlbums()

        summary = SyncService(session, albums).sync()

        assert len(summary.identities) == 2

        by_species = {item.species: item for item in summary.identities}

        assert by_species["dog"].identity == "Max"
        assert by_species["dog"].assets == 1
        assert by_species["cat"].identity == "Max"
        assert by_species["cat"].assets == 1

        assert sorted(albums.calls) == [
            ("Max", ["cat-asset"], "cat"),
            ("Max", ["dog-asset"], "dog"),
        ]


def test_sync_dry_run_does_not_update(engine):
    with Session(engine) as session:
        asset = Asset(
            immich_asset_id="asset1",
            checksum="abc",
            extension=".jpg",
        )

        detection = Detection(
            asset=asset,
            label="dog",
            confidence=1.0,
            x1=0,
            y1=0,
            x2=10,
            y2=10,
        )

        crop = Crop(
            detection=detection,
            path="crop.jpg",
        )

        classification = CropClassification(
            crop=crop,
            identity="Fibs",
            confidence=0.95,
        )

        session.add(classification)
        session.commit()

        albums = FakeAlbums()

        summary = SyncService(
            session,
            albums,
        ).sync(
            dry_run=True,
        )

        assert summary.identities[0].identity == "Fibs"
        assert summary.identities[0].assets == 1

        assert albums.calls == []


def test_sync_removes_stale_membership_after_correction(engine):
    """DT-1113 core regression test: classify an asset to identity A, sync
    (added to A's album), correct it to identity B, sync again -- the asset
    must be removed from A's album and added to B's, not left in both."""
    with Session(engine) as session:
        asset = Asset(immich_asset_id="asset1", checksum="abc", extension=".jpg")

        detection = Detection(
            asset=asset, label="dog", confidence=1.0, x1=0, y1=0, x2=10, y2=10
        )

        crop = Crop(detection=detection, path="crop.jpg")

        classification = CropClassification(crop=crop, identity="Fibs", confidence=0.95)

        session.add(classification)
        session.commit()

        albums = FakeAlbums()
        service = SyncService(session, albums)

        service.sync()

        assert albums.calls == [("Fibs", ["asset1"], "dog")]
        assert albums.removals == []

        # Correct the classification to a different identity, matching
        # what ClassificationCorrectionService.correct() does to this
        # column (no need for the full service here -- sync() only reads
        # CropClassification.identity/confidence).
        classification.identity = "Hermann"
        session.commit()

        albums.calls = []

        service.sync()

        assert albums.calls == [("Hermann", ["asset1"], "dog")]
        assert albums.removals == [("Fibs", ["asset1"], "dog")]


def test_sync_removes_stale_membership_after_correction_to_unknown(engine):
    """Correcting to Unknown with include_unknown=False (the default) must
    still remove the asset from its previous identity's album, even though
    no Unknown album involvement happens on the add side."""
    with Session(engine) as session:
        asset = Asset(immich_asset_id="asset1", checksum="abc", extension=".jpg")

        detection = Detection(
            asset=asset, label="dog", confidence=1.0, x1=0, y1=0, x2=10, y2=10
        )

        crop = Crop(detection=detection, path="crop.jpg")

        classification = CropClassification(crop=crop, identity="Fibs", confidence=0.95)

        session.add(classification)
        session.commit()

        albums = FakeAlbums()
        service = SyncService(session, albums, policy=SyncPolicy(include_unknown=False))

        service.sync()

        assert albums.calls == [("Fibs", ["asset1"], "dog")]

        classification.identity = None
        session.commit()

        albums.calls = []

        service.sync()

        assert albums.calls == []
        assert albums.removals == [("Fibs", ["asset1"], "dog")]


def test_sync_is_idempotent_with_no_new_corrections(engine):
    """Re-running sync with nothing changed must not call remove_from_identity
    at all -- this ticket adds removal only for assets whose identity
    actually changed since the last sync, not a full album rebuild every
    run."""
    with Session(engine) as session:
        asset = Asset(immich_asset_id="asset1", checksum="abc", extension=".jpg")

        detection = Detection(
            asset=asset, label="dog", confidence=1.0, x1=0, y1=0, x2=10, y2=10
        )

        crop = Crop(detection=detection, path="crop.jpg")

        classification = CropClassification(crop=crop, identity="Fibs", confidence=0.95)

        session.add(classification)
        session.commit()

        albums = FakeAlbums()
        service = SyncService(session, albums)

        service.sync()
        service.sync()
        service.sync()

        assert albums.removals == []


def test_sync_dry_run_does_not_persist_synced_state_or_remove(engine):
    with Session(engine) as session:
        asset = Asset(immich_asset_id="asset1", checksum="abc", extension=".jpg")

        detection = Detection(
            asset=asset, label="dog", confidence=1.0, x1=0, y1=0, x2=10, y2=10
        )

        crop = Crop(detection=detection, path="crop.jpg")

        classification = CropClassification(crop=crop, identity="Fibs", confidence=0.95)

        session.add(classification)
        session.commit()

        albums = FakeAlbums()
        service = SyncService(session, albums)

        service.sync(dry_run=True)

        assert albums.calls == []
        assert albums.removals == []
        assert session.query(SyncedAsset).count() == 0


def test_sync_reports_skipped_low_confidence_classifications(engine):
    """Issue #11: a sync producing fewer albums than expected must say why
    -- not just silently omit the low-confidence classifications."""
    with Session(engine) as session:
        for i, confidence in enumerate([0.95, 0.50, 0.10]):
            asset = Asset(immich_asset_id=f"asset{i}", checksum="c", extension=".jpg")
            detection = Detection(
                asset=asset, label="dog", confidence=1.0, x1=0, y1=0, x2=10, y2=10
            )
            crop = Crop(detection=detection, path=f"crop{i}.jpg")
            session.add(
                CropClassification(crop=crop, identity="Fibs", confidence=confidence)
            )
        session.commit()

        albums = FakeAlbums()
        summary = SyncService(session, albums).sync()

        assert len(summary.identities) == 1
        assert summary.identities[0].assets == 1
        assert summary.skipped_low_confidence == 2
        assert summary.skipped_unknown == 0
        assert summary.skipped_missing_asset == 0


def test_sync_reports_skipped_unknown_classifications(engine):
    with Session(engine) as session:
        asset = Asset(immich_asset_id="asset1", checksum="c", extension=".jpg")
        detection = Detection(
            asset=asset, label="dog", confidence=1.0, x1=0, y1=0, x2=10, y2=10
        )
        crop = Crop(detection=detection, path="crop.jpg")

        # Manually corrected to Unknown: confidence is 1.0 (matching what
        # ClassificationCorrectionService.correct() sets), so this is only
        # excluded by the identity=None/include_unknown check, not the
        # confidence one -- the two skip reasons must stay distinct.
        session.add(CropClassification(crop=crop, identity=None, confidence=1.0))
        session.commit()

        albums = FakeAlbums()
        summary = SyncService(session, albums).sync()

        assert len(summary.identities) == 0
        assert summary.skipped_low_confidence == 0
        assert summary.skipped_unknown == 1
        assert albums.calls == []


def test_sync_skips_classification_missing_detection_instead_of_crashing(engine):
    """A crop with no resolvable Detection (e.g. an orphaned row) used to
    raise, aborting sync() before a single album was touched -- one bad row
    meant zero albums synced that run, not "everything else still went
    through". It must now be skipped and counted instead."""
    with Session(engine) as session:
        orphaned_crop = Crop(detection_id=999, path="orphaned.jpg")

        good_asset = Asset(immich_asset_id="asset1", checksum="c", extension=".jpg")
        good_detection = Detection(
            asset=good_asset, label="dog", confidence=1.0, x1=0, y1=0, x2=10, y2=10
        )
        good_crop = Crop(detection=good_detection, path="good.jpg")

        session.add_all(
            [
                CropClassification(
                    crop=orphaned_crop, identity="Fibs", confidence=0.95
                ),
                CropClassification(crop=good_crop, identity="Hermann", confidence=0.95),
            ]
        )
        session.commit()

        albums = FakeAlbums()
        summary = SyncService(session, albums).sync()

        assert summary.skipped_missing_asset == 1
        assert len(summary.identities) == 1
        assert summary.identities[0].identity == "Hermann"
        assert albums.calls == [("Hermann", ["asset1"], "dog")]


def test_sync_full_accounting_matches_issue_11_scenario(engine):
    """Reproduces the reported scenario: several reviewed/classified
    animals, but only some are eligible to sync -- the summary must account
    for all of them, not just the ones that made it into an album."""
    with Session(engine) as session:
        # 3 confidently classified (reviewed) -- expected to sync.
        for i, identity in enumerate(["Fibs", "Hermann", "Henri"]):
            asset = Asset(immich_asset_id=f"good-{i}", checksum="c", extension=".jpg")
            detection = Detection(
                asset=asset, label="dog", confidence=1.0, x1=0, y1=0, x2=10, y2=10
            )
            crop = Crop(detection=detection, path=f"good-{i}.jpg")
            session.add(
                CropClassification(crop=crop, identity=identity, confidence=1.0)
            )

        # 2 auto-classified but never reviewed, below the sync threshold.
        for i in range(2):
            asset = Asset(
                immich_asset_id=f"low-conf-{i}", checksum="c", extension=".jpg"
            )
            detection = Detection(
                asset=asset, label="dog", confidence=1.0, x1=0, y1=0, x2=10, y2=10
            )
            crop = Crop(detection=detection, path=f"low-conf-{i}.jpg")
            session.add(
                CropClassification(crop=crop, identity="Cooper", confidence=0.55)
            )

        # 1 manually corrected to Unknown -- confidence 1.0 (matching what
        # ClassificationCorrectionService.correct() sets), so it's excluded
        # by the identity=None check, not the confidence one.
        asset = Asset(immich_asset_id="unknown-1", checksum="c", extension=".jpg")
        detection = Detection(
            asset=asset, label="dog", confidence=1.0, x1=0, y1=0, x2=10, y2=10
        )
        crop = Crop(detection=detection, path="unknown-1.jpg")
        session.add(CropClassification(crop=crop, identity=None, confidence=1.0))

        session.commit()

        albums = FakeAlbums()
        summary = SyncService(session, albums).sync()

        assert len(summary.identities) == 3
        assert summary.skipped_low_confidence == 2
        assert summary.skipped_unknown == 1
        assert summary.skipped_missing_asset == 0

        # The full count is always reconstructable from the summary alone.
        total_accounted_for = (
            len(summary.identities)
            + summary.skipped_low_confidence
            + summary.skipped_unknown
            + summary.skipped_missing_asset
        )
        assert total_accounted_for == 6
