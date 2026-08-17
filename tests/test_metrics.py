from sqlalchemy.orm import Session

from immich_dog_tagger.enums import ClassificationPassStatus, ReviewActions, Species
from immich_dog_tagger.models import (
    ClassificationPass,
    Crop,
    CropClassification,
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
