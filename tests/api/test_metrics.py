from sqlalchemy.orm import Session

from immich_dog_tagger.enums import AssetStatus
from immich_dog_tagger.models import Asset, Crop, CropClassification, Detection
from tests.conftest import QueryCounter


def test_metrics_empty_project(api_client):
    response = api_client.get("/metrics")

    assert response.status_code == 200

    payload = response.json()
    assert payload["eligible_count"] == 0
    assert payload["coverage"] is None
    assert payload["review_rate"] is None
    assert payload["unknown_rate"] is None
    assert payload["automation_rate"] is None
    assert payload["review_queue_size"] == 0
    assert payload["no_review_needed_count"] == 0
    assert payload["last_reclassification"] is None
    assert payload["pass_history"] == []


def test_metrics_reflects_classification_counts(api_client, engine):
    with Session(engine) as session:
        crop = Crop(detection_id=1, path="dog.jpg")
        session.add(crop)
        session.flush()

        session.add(
            CropClassification(
                crop=crop,
                identity="Hermann",
                confidence=0.95,
            )
        )
        session.commit()

    response = api_client.get("/metrics")

    assert response.status_code == 200
    payload = response.json()
    assert payload["eligible_count"] == 1
    assert payload["confident_count"] == 1
    assert payload["coverage"] == 1.0
    assert payload["automation_rate"] == 1.0
    assert payload["no_review_needed_count"] == 1
    assert payload["review_queue_size"] == 0


def _detected_asset(session, immich_asset_id, *, with_crop):
    asset = Asset(
        immich_asset_id=immich_asset_id,
        extension="jpg",
        status=AssetStatus.DETECTED,
    )
    session.add(asset)
    session.flush()

    if with_crop:
        detection = Detection(
            asset_id=asset.id,
            label="dog",
            confidence=0.9,
            x1=0,
            y1=0,
            x2=10,
            y2=10,
        )
        session.add(detection)
        session.flush()

        session.add(Crop(detection_id=detection.id, path=f"{immich_asset_id}.jpg"))


def test_metrics_reports_detection_coverage(api_client, engine):
    with Session(engine) as session:
        _detected_asset(session, "with-dog", with_crop=True)
        _detected_asset(session, "no-pet-1", with_crop=False)
        _detected_asset(session, "no-pet-2", with_crop=False)

        session.add(
            Asset(
                immich_asset_id="not-yet-detected",
                extension="jpg",
                status=AssetStatus.PENDING,
            )
        )
        session.commit()

    payload = api_client.get("/metrics").json()

    coverage = payload["detection_coverage"]

    assert coverage["scanned_count"] == 4
    assert coverage["processed_count"] == 3
    assert coverage["with_crops_count"] == 1
    assert coverage["without_crops_count"] == 2
    assert coverage["awaiting_detection_count"] == 1
    assert coverage["unprocessable_count"] == 0
    assert coverage["with_crops_rate"] == 1 / 3


def test_metrics_empty_project_reports_detection_coverage_without_a_rate(api_client):
    coverage = api_client.get("/metrics").json()["detection_coverage"]

    assert coverage["scanned_count"] == 0
    assert coverage["processed_count"] == 0
    assert coverage["with_crops_rate"] is None


def test_metrics_query_count_does_not_scale_with_library_size(api_client, engine):
    """
    The detection-coverage counts are photo-denominated, so a per-asset
    query here would be an N+1 over the whole library rather than over the
    classified crops. Query count must stay flat as the library grows.
    """

    def seed(offset, count):
        with Session(engine) as session:
            for index in range(offset, offset + count):
                _detected_asset(session, f"asset-{index}", with_crop=index % 2 == 0)
            session.commit()

    seed(0, 10)

    with QueryCounter(engine) as small:
        assert api_client.get("/metrics").status_code == 200

    seed(10, 90)

    with QueryCounter(engine) as large:
        assert api_client.get("/metrics").status_code == 200

    assert large.count == small.count
