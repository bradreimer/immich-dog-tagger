from sqlalchemy.orm import Session

from immich_dog_tagger.enums import (
    AssetStatus,
    ClassificationPassStatus,
    ReviewActions,
    Species,
)
from immich_dog_tagger.models import (
    Asset,
    ClassificationPass,
    Crop,
    CropClassification,
    Detection,
    EmbeddingExample,
    EmbeddingSources,
    Identity,
    ReviewAction,
)
from immich_dog_tagger.services.metrics import MetricsService


def _classification(session, *, identity, confidence, species=Species.DOG):
    crop = Crop(
        detection_id=1,
        path=f"{identity or 'unknown'}-{confidence}.jpg",
        species=species,
    )
    session.add(crop)
    session.flush()

    classification = CropClassification(
        crop=crop, identity=identity, confidence=confidence
    )
    session.add(classification)
    session.flush()

    return classification


def test_learning_metrics_counts_and_ratios(engine):
    with Session(engine) as session:
        _classification(session, identity="Hermann", confidence=0.95)  # confident
        reviewed = _classification(
            session, identity="Fibs", confidence=1.0
        )  # confident, reviewed
        _classification(session, identity=None, confidence=-1.0)  # unknown
        _classification(session, identity="Hermann", confidence=0.5)  # needs review

        session.add(
            ReviewAction(
                classification_id=reviewed.id,
                action=ReviewActions.CORRECT,
                identity="Fibs",
            )
        )

        identity = Identity(name="Hermann")
        session.add(identity)
        session.flush()
        session.add(
            EmbeddingExample(
                identity_id=identity.id,
                crop_path="hermann.jpg",
                embedding=b"123",
                source=EmbeddingSources.BOOTSTRAP,
            )
        )

        session.commit()

        metrics = MetricsService(session).learning_metrics()

        assert metrics.eligible_count == 4
        assert metrics.confident_count == 2
        assert metrics.needs_review_count == 1
        assert metrics.unknown_count == 1
        assert metrics.reviewed_count == 1
        assert metrics.labeled_example_count == 1
        assert metrics.coverage == 0.5
        assert metrics.review_rate == 0.25
        assert metrics.unknown_rate == 0.25
        # Reviewed items and confident AUTO items don't need manual review;
        # the unknown crop and the below-threshold Hermann crop do.
        assert metrics.review_queue_size == 2
        assert metrics.no_review_needed_count == 2
        assert metrics.automation_rate == 0.5
        assert metrics.last_reclassification is None
        assert metrics.pass_history == []


def test_learning_metrics_with_no_data_reports_none_ratios(engine):
    with Session(engine) as session:
        metrics = MetricsService(session).learning_metrics()

        assert metrics.eligible_count == 0
        assert metrics.coverage is None
        assert metrics.review_rate is None
        assert metrics.unknown_rate is None
        assert metrics.automation_rate is None
        assert metrics.review_queue_size == 0
        assert metrics.no_review_needed_count == 0


def test_learning_metrics_reports_pass_history_and_last_reclassification(engine):
    with Session(engine) as session:
        session.add(
            ClassificationPass(
                status=ClassificationPassStatus.COMPLETED,
                classifier_version="v1",
                threshold=0.80,
                eligible_count=10,
                confident_count=8,
                unknown_count=2,
                changed_count=3,
                labeled_example_count=40,
                review_queue_size=2,
            )
        )
        session.commit()

        second = ClassificationPass(
            status=ClassificationPassStatus.COMPLETED,
            classifier_version="v1",
            threshold=0.80,
            eligible_count=10,
            confident_count=9,
            unknown_count=1,
            changed_count=1,
            labeled_example_count=55,
            review_queue_size=1,
        )
        session.add(second)
        session.commit()

        metrics = MetricsService(session).learning_metrics()

        assert len(metrics.pass_history) == 2
        # Oldest first, so a trend chart reads left-to-right chronologically.
        assert metrics.pass_history[0].confident_count == 8
        assert metrics.pass_history[0].labeled_example_count == 40
        assert metrics.pass_history[0].review_queue_size == 2
        assert metrics.pass_history[1].confident_count == 9
        assert metrics.pass_history[1].labeled_example_count == 55
        assert metrics.pass_history[1].review_queue_size == 1

        assert metrics.last_reclassification is not None
        assert metrics.last_reclassification.id == second.id
        assert metrics.last_reclassification.changed_count == 1
        assert metrics.last_reclassification.labeled_example_count == 55


def test_pass_summary_trend_fields_are_null_for_legacy_or_failed_passes(engine):
    with Session(engine) as session:
        session.add(
            ClassificationPass(
                status=ClassificationPassStatus.FAILED,
                classifier_version="v1",
                threshold=0.80,
                eligible_count=10,
            )
        )
        session.commit()

        metrics = MetricsService(session).learning_metrics()

        assert metrics.last_reclassification is not None
        assert metrics.last_reclassification.labeled_example_count is None
        assert metrics.last_reclassification.review_queue_size is None


def test_learning_metrics_history_limit(engine):
    with Session(engine) as session:
        for i in range(15):
            session.add(
                ClassificationPass(
                    status=ClassificationPassStatus.COMPLETED,
                    classifier_version="v1",
                    threshold=0.80,
                    eligible_count=i,
                )
            )
        session.commit()

        metrics = MetricsService(session, history_limit=5).learning_metrics()

        assert len(metrics.pass_history) == 5
        # Most recent 5, oldest-first.
        assert [p.eligible_count for p in metrics.pass_history] == [10, 11, 12, 13, 14]


def test_learning_metrics_default_history_limit_covers_more_than_ten_passes(engine):
    with Session(engine) as session:
        for i in range(30):
            session.add(
                ClassificationPass(
                    status=ClassificationPassStatus.COMPLETED,
                    classifier_version="v1",
                    threshold=0.80,
                    eligible_count=i,
                )
            )
        session.commit()

        metrics = MetricsService(session).learning_metrics()

        # Default history_limit must exceed 10 so the full history is
        # returned instead of a moving 10-pass window -- downsampling for
        # display is the UI's job, not this service's.
        assert len(metrics.pass_history) == 30
        assert metrics.pass_history[0].eligible_count == 0
        assert metrics.pass_history[-1].eligible_count == 29


def test_species_breakdown_keys_off_crop_species_not_detection_label(engine):
    """
    A species-corrected crop must be counted under its corrected species
    (Crop.species), not whatever the detector originally guessed
    (Detection.label) -- the two only ever diverge after a species
    correction, which this test simulates directly by giving the crop a
    species with no backing Detection row at all.
    """
    with Session(engine) as session:
        _classification(
            session, identity="Whiskers", confidence=0.95, species=Species.CAT
        )
        _classification(
            session, identity="Hermann", confidence=0.95, species=Species.DOG
        )

        session.commit()

        metrics = MetricsService(session).learning_metrics()

        by_species = {entry.species: entry for entry in metrics.by_species}

        assert by_species["cat"].eligible_count == 1
        assert by_species["cat"].confident_count == 1
        assert by_species["dog"].eligible_count == 1
        assert by_species["dog"].confident_count == 1


def _asset(session, immich_asset_id, status, *, crops=0, species=Species.DOG):
    asset = Asset(
        immich_asset_id=immich_asset_id,
        extension="jpg",
        status=status,
    )
    session.add(asset)
    session.flush()

    for index in range(crops):
        detection = Detection(
            asset_id=asset.id,
            label=species.value,
            confidence=0.9,
            x1=0,
            y1=0,
            x2=10,
            y2=10,
        )
        session.add(detection)
        session.flush()

        session.add(
            Crop(
                detection_id=detection.id,
                path=f"{immich_asset_id}-{index}.jpg",
                species=species,
            )
        )

    session.flush()

    return asset


def test_detection_coverage_counts_photos_in_every_status(engine):
    """
    Issue #146: the only figure here whose denominator is photos rather
    than CropClassification rows, so an asset detection found nothing in
    has to be visible as its own count instead of silently missing.
    """
    with Session(engine) as session:
        _asset(session, "detected-two-dogs", AssetStatus.DETECTED, crops=2)
        _asset(session, "detected-one-dog", AssetStatus.DETECTED, crops=1)
        _asset(session, "detected-no-pet", AssetStatus.DETECTED)
        _asset(session, "detected-no-pet-2", AssetStatus.DETECTED)
        _asset(session, "classified", AssetStatus.CLASSIFIED, crops=1)
        _asset(session, "tagged", AssetStatus.TAGGED, crops=1)
        _asset(session, "classify-failed", AssetStatus.CLASSIFICATION_FAILED)
        _asset(session, "scanned", AssetStatus.PENDING)
        _asset(session, "downloaded", AssetStatus.DOWNLOADED)
        _asset(session, "download-failed", AssetStatus.DOWNLOAD_FAILED)
        _asset(session, "detect-failed", AssetStatus.DETECTION_FAILED)
        _asset(session, "unsupported", AssetStatus.UNSUPPORTED)

        session.commit()

        coverage = MetricsService(session).learning_metrics().detection_coverage

        assert coverage.scanned_count == 12
        # detected x4 + classified + tagged + classification_failed
        assert coverage.processed_count == 7
        # Photos, not crops: the two-dog photo counts once.
        assert coverage.with_crops_count == 4
        assert coverage.without_crops_count == 3
        assert coverage.awaiting_detection_count == 2
        assert coverage.unprocessable_count == 3
        assert coverage.with_crops_rate == 4 / 7


def test_detection_coverage_has_no_rate_before_detection_runs(engine):
    """
    A library that has only been scanned has no honest coverage figure
    yet -- report None rather than 0%, which would read as "detection
    found nothing".
    """
    with Session(engine) as session:
        _asset(session, "scanned", AssetStatus.PENDING)
        _asset(session, "downloaded", AssetStatus.DOWNLOADED)

        session.commit()

        coverage = MetricsService(session).learning_metrics().detection_coverage

        assert coverage.scanned_count == 2
        assert coverage.processed_count == 0
        assert coverage.with_crops_count == 0
        assert coverage.without_crops_count == 0
        assert coverage.awaiting_detection_count == 2
        assert coverage.with_crops_rate is None


def test_detection_coverage_ignores_crops_on_assets_awaiting_redetection(engine):
    """
    A rescanned asset goes back to PENDING while keeping the crops from
    its previous detection run. Those crops must not be counted against a
    denominator that excludes the asset, or with_crops_count could exceed
    processed_count and the rate could exceed 100%.
    """
    with Session(engine) as session:
        _asset(session, "rescanned", AssetStatus.PENDING, crops=1)
        _asset(session, "detected", AssetStatus.DETECTED, crops=1)

        session.commit()

        coverage = MetricsService(session).learning_metrics().detection_coverage

        assert coverage.processed_count == 1
        assert coverage.with_crops_count == 1
        assert coverage.without_crops_count == 0
        assert coverage.with_crops_rate == 1.0


def test_detection_coverage_does_not_shift_the_crop_based_metrics(engine):
    """
    Regression pin for the #115 failure mode: adding a photo-denominator
    figure must not redefine automation rate or confident coverage, whose
    denominator stays the number of classified crops -- so photos that
    produced no crop change nothing here.
    """
    with Session(engine) as session:
        _classification(session, identity="Hermann", confidence=0.95)
        _classification(session, identity="Hermann", confidence=0.5)

        # Ten photos detection found no pet in: the exact population the
        # new coverage figure exists to surface, and the exact population
        # the older figures must keep ignoring.
        for index in range(10):
            _asset(session, f"no-pet-{index}", AssetStatus.DETECTED)

        session.commit()

        metrics = MetricsService(session).learning_metrics()

        assert metrics.eligible_count == 2
        assert metrics.confident_count == 1
        assert metrics.coverage == 0.5
        assert metrics.review_queue_size == 1
        assert metrics.no_review_needed_count == 1
        assert metrics.automation_rate == 0.5

        assert metrics.detection_coverage.processed_count == 10
        assert metrics.detection_coverage.without_crops_count == 10
        assert metrics.detection_coverage.with_crops_rate == 0.0
