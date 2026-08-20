from datetime import UTC, datetime

import numpy as np
import pytest
from sqlalchemy.orm import Session

from immich_dog_tagger.embeddings import embedding_to_blob
from immich_dog_tagger.enums import ReviewActions, Species
from immich_dog_tagger.models import (
    Asset,
    Crop,
    CropClassification,
    Detection,
    EmbeddingExample,
    Identity,
    ReviewAction,
)
from tests.conftest import QueryCounter


def test_library_returns_reviewed_and_unreviewed(api_client, engine):
    with Session(engine) as session:
        reviewed_crop = Crop(detection_id=1, path="reviewed.jpg")
        unreviewed_crop = Crop(detection_id=1, path="unreviewed.jpg")

        session.add_all([reviewed_crop, unreviewed_crop])
        session.flush()

        reviewed = CropClassification(
            crop=reviewed_crop,
            identity="Fibs",
            confidence=0.95,
        )
        unreviewed = CropClassification(
            crop=unreviewed_crop,
            identity="Hermann",
            confidence=0.60,
        )

        session.add_all([reviewed, unreviewed])
        session.flush()

        session.add(
            ReviewAction(
                classification_id=reviewed.id,
                action=ReviewActions.CORRECT,
                identity="Fibs",
            )
        )
        session.commit()

    response = api_client.get("/library")

    assert response.status_code == 200

    payload = response.json()

    assert payload["total"] == 2
    assert payload["limit"] == 50
    assert payload["offset"] == 0
    assert len(payload["items"]) == 2

    reviewed_flags = {entry["reviewed"] for entry in payload["items"]}
    assert reviewed_flags == {True, False}


def test_library_filters_by_query_params(api_client, engine):
    with Session(engine) as session:
        asset = Asset(
            immich_asset_id="asset-1",
            extension=".jpg",
            captured_at=datetime(2019, 3, 3, tzinfo=UTC),
        )
        detection = Detection(
            asset=asset, label="dog", confidence=0.9, x1=0, y1=0, x2=1, y2=1
        )
        crop = Crop(detection=detection, path="fibs.jpg")

        session.add(crop)
        session.flush()

        session.add(CropClassification(crop=crop, identity="Fibs", confidence=0.9))
        session.commit()

    response = api_client.get(
        "/library",
        params={
            "identity": "Fibs",
            "species": "dog",
            "reviewed": "false",
            "captured_after": "2019-01-01T00:00:00",
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["total"] == 1
    assert payload["items"][0]["item"]["captured_at"] == "2019-03-03T00:00:00"


def test_library_pagination_params(api_client, engine):
    with Session(engine) as session:
        for i in range(5):
            crop = Crop(detection_id=1, path=f"dog-{i}.jpg")
            session.add(crop)
            session.flush()
            session.add(CropClassification(crop=crop, identity="Fibs", confidence=0.9))
        session.commit()

    response = api_client.get("/library", params={"limit": 2, "offset": 2})

    assert response.status_code == 200

    payload = response.json()

    assert payload["total"] == 5
    assert payload["limit"] == 2
    assert payload["offset"] == 2
    assert len(payload["items"]) == 2


def test_review_queue_unaffected_by_library_route(api_client, engine):
    """DT-1112 acceptance criterion: the existing GET /review queue endpoint
    is unchanged in behavior by the addition of GET /library."""
    with Session(engine) as session:
        reviewed_crop = Crop(detection_id=1, path="reviewed.jpg")

        session.add(reviewed_crop)
        session.flush()

        reviewed = CropClassification(
            crop=reviewed_crop,
            identity="Fibs",
            confidence=0.95,
        )

        session.add(reviewed)
        session.flush()

        session.add(
            ReviewAction(
                classification_id=reviewed.id,
                action=ReviewActions.CORRECT,
                identity="Fibs",
            )
        )
        session.commit()

    review_response = api_client.get("/review")
    library_response = api_client.get("/library")

    assert review_response.status_code == 200
    assert library_response.status_code == 200

    # The reviewed item must still be excluded from the queue...
    assert review_response.json() == []

    # ...but present in the library.
    assert library_response.json()["total"] == 1


def _seed_pet_with_candidates(session, count=3, species=Species.DOG):
    session.add(Identity(name="Fibs", species=species))
    session.flush()

    classifications = []

    for index in range(count):
        asset = Asset(
            immich_asset_id=f"asset-{index}",
            extension=".jpg",
            captured_at=datetime(2026, 1, index + 1, tzinfo=UTC),
        )
        detection = Detection(
            asset=asset,
            label=species.value,
            confidence=0.9,
            x1=0,
            y1=0,
            x2=1,
            y2=1,
        )
        crop = Crop(detection=detection, path=f"fibs-{index}.jpg", species=species)

        session.add(crop)
        session.flush()

        classification = CropClassification(
            crop=crop,
            identity="Fibs",
            confidence=0.70 + index / 100,
            embedding=embedding_to_blob(np.array([1, 0, 0], dtype=np.float32)),
        )

        session.add(classification)
        classifications.append(classification)

    session.commit()

    return [classification.id for classification in classifications]


def test_clusters_endpoint_returns_clusters_for_a_pet(api_client, engine):
    with Session(engine) as session:
        classification_ids = _seed_pet_with_candidates(session)

    response = api_client.get("/library/clusters?identity=Fibs&species=dog")

    assert response.status_code == 200

    payload = response.json()

    assert payload["identity"] == "Fibs"
    assert payload["species"] == "dog"
    assert payload["candidate_count"] == 3
    assert payload["clustered_count"] == 3
    assert payload["truncated"] is False
    assert payload["excluded"] == []
    assert len(payload["clusters"]) == 1

    cluster = payload["clusters"][0]

    assert cluster["size"] == 3
    assert cluster["representative"]["image_url"].startswith("/crops/")
    # Default sort is confidence descending (issue #143) -- the surest
    # member first, which for this fixture is also the highest id.
    assert [member["classification_id"] for member in cluster["members"]] == list(
        reversed(classification_ids)
    )
    assert cluster["min_similarity"] == pytest.approx(0.70)
    assert cluster["max_similarity"] == pytest.approx(0.72)
    assert cluster["earliest_captured_at"].startswith("2026-01-01")
    assert cluster["latest_captured_at"].startswith("2026-01-03")
    assert payload["sort"] == "confidence_desc"


def test_clusters_endpoint_accepts_a_sort_query_param(api_client, engine):
    with Session(engine) as session:
        classification_ids = _seed_pet_with_candidates(session)

    response = api_client.get(
        "/library/clusters?identity=Fibs&species=dog&sort=captured_asc"
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["sort"] == "captured_asc"
    # Ascending capture date matches ascending id for this fixture.
    assert [
        member["classification_id"] for member in payload["clusters"][0]["members"]
    ] == classification_ids


def test_clusters_endpoint_rejects_an_unknown_sort(api_client, engine):
    with Session(engine) as session:
        _seed_pet_with_candidates(session)

    response = api_client.get(
        "/library/clusters?identity=Fibs&species=dog&sort=alphabetical"
    )

    assert response.status_code == 422


def test_clusters_endpoint_is_empty_for_a_pet_with_no_candidates(api_client, engine):
    with Session(engine) as session:
        session.add(Identity(name="Fibs", species=Species.DOG))
        session.commit()

    response = api_client.get("/library/clusters?identity=Fibs&species=dog")

    assert response.status_code == 200
    assert response.json()["clusters"] == []
    assert response.json()["candidate_count"] == 0


def test_clusters_endpoint_404s_for_an_unknown_pet(api_client, engine):
    response = api_client.get("/library/clusters?identity=Nobody&species=dog")

    assert response.status_code == 404


def test_approve_endpoint_applies_and_reports_skips(api_client, engine):
    with Session(engine) as session:
        classification_ids = _seed_pet_with_candidates(session)

    response = api_client.post(
        "/library/clusters/approve",
        json={
            "identity": "Fibs",
            "species": "dog",
            "classification_ids": [*classification_ids, 9999],
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["identity"] == "Fibs"
    assert payload["applied"] == 3
    assert payload["skipped"] == 1
    assert payload["skips"] == [{"classification_id": 9999, "reason": "not-found"}]

    with Session(engine) as session:
        assert session.query(ReviewAction).count() == 3
        assert session.query(EmbeddingExample).count() == 3

    # The approved members are no longer pending candidates.
    assert (
        api_client.get("/library/clusters?identity=Fibs&species=dog").json()[
            "candidate_count"
        ]
        == 0
    )


def test_approve_endpoint_applies_to_exactly_the_submitted_selection(
    api_client, engine
):
    """A deselected member (issue #142) is left pending, not swept in."""
    with Session(engine) as session:
        classification_ids = _seed_pet_with_candidates(session)

    selected = classification_ids[:2]

    response = api_client.post(
        "/library/clusters/approve",
        json={
            "identity": "Fibs",
            "species": "dog",
            "classification_ids": selected,
        },
    )

    assert response.status_code == 200
    assert response.json()["applied"] == 2

    with Session(engine) as session:
        assert session.query(ReviewAction).count() == 2

    # The deselected member is still waiting to be reviewed.
    payload = api_client.get("/library/clusters?identity=Fibs&species=dog").json()

    assert payload["candidate_count"] == 1
    assert [
        member["classification_id"] for member in payload["clusters"][0]["members"]
    ] == classification_ids[2:]


def test_approve_endpoint_rejects_an_empty_selection(api_client, engine):
    with Session(engine) as session:
        _seed_pet_with_candidates(session)

    response = api_client.post(
        "/library/clusters/approve",
        json={
            "identity": "Fibs",
            "species": "dog",
            "classification_ids": [],
        },
    )

    assert response.status_code == 422

    with Session(engine) as session:
        assert session.query(ReviewAction).count() == 0


def test_approve_endpoint_400s_for_an_unknown_pet(api_client, engine):
    response = api_client.post(
        "/library/clusters/approve",
        json={
            "identity": "Nobody",
            "species": "dog",
            "classification_ids": [1],
        },
    )

    assert response.status_code == 400


def test_clusters_endpoint_query_count_is_independent_of_pool_size(api_client, engine):
    with Session(engine) as session:
        _seed_pet_with_candidates(session, count=3)

    with QueryCounter(engine) as small:
        api_client.get("/library/clusters?identity=Fibs&species=dog")

    with Session(engine) as session:
        session.query(CropClassification).delete()
        session.query(Crop).delete()
        session.query(Detection).delete()
        session.query(Asset).delete()
        session.query(Identity).delete()
        session.commit()

    with Session(engine) as session:
        _seed_pet_with_candidates(session, count=30)

    with QueryCounter(engine) as large:
        api_client.get("/library/clusters?identity=Fibs&species=dog")

    assert small.count == large.count


def test_clusters_endpoint_query_count_is_independent_of_sort(api_client, engine):
    """Sorting reorders an already-loaded result set; it must not add a query."""
    with Session(engine) as session:
        _seed_pet_with_candidates(session, count=10)

    with QueryCounter(engine) as unsorted:
        api_client.get("/library/clusters?identity=Fibs&species=dog")

    with QueryCounter(engine) as sorted_by_date:
        api_client.get("/library/clusters?identity=Fibs&species=dog&sort=captured_asc")

    assert unsorted.count == sorted_by_date.count


def test_reject_endpoint_records_not_this_pet_and_drops_them_from_the_pool(
    api_client, engine
):
    """
    A rejected recommendation must not come back next pass -- the gap that
    made "skip" the only way to dismiss a wrong proposal (issue #144).
    """
    with Session(engine) as session:
        classification_ids = _seed_pet_with_candidates(session)

    rejected = classification_ids[:2]

    response = api_client.post(
        "/library/clusters/reject",
        json={
            "identity": "Fibs",
            "species": "dog",
            "classification_ids": rejected,
        },
    )

    assert response.status_code == 200
    assert response.json()["applied"] == 2
    assert response.json()["skipped"] == 0

    payload = api_client.get("/library/clusters?identity=Fibs&species=dog").json()

    # Only the member that was not rejected is still proposed as Fibs.
    assert payload["candidate_count"] == 1

    remaining = [
        member["classification_id"]
        for cluster in payload["clusters"]
        for member in cluster["members"]
    ]

    assert remaining == classification_ids[2:]


def test_reject_endpoint_settles_no_identity(api_client, engine):
    with Session(engine) as session:
        classification_ids = _seed_pet_with_candidates(session)

    api_client.post(
        "/library/clusters/reject",
        json={
            "identity": "Fibs",
            "species": "dog",
            "classification_ids": classification_ids[:1],
        },
    )

    with Session(engine) as session:
        classification = session.get(CropClassification, classification_ids[0])

        # Not Fibs, and not silently relabelled as anything else either.
        assert classification.identity != "Fibs"
        assert classification.review_actions == []


def test_reject_endpoint_rejects_an_empty_selection(api_client, engine):
    with Session(engine) as session:
        _seed_pet_with_candidates(session)

    response = api_client.post(
        "/library/clusters/reject",
        json={
            "identity": "Fibs",
            "species": "dog",
            "classification_ids": [],
        },
    )

    assert response.status_code == 422


def test_reject_endpoint_400s_for_an_unknown_pet(api_client, engine):
    with Session(engine) as session:
        classification_ids = _seed_pet_with_candidates(session)

    response = api_client.post(
        "/library/clusters/reject",
        json={
            "identity": "Nobody",
            "species": "dog",
            "classification_ids": classification_ids[:1],
        },
    )

    assert response.status_code == 400
