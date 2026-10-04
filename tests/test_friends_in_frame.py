from sqlalchemy.orm import Session

from immich_dog_tagger.enums import ClassificationSources, Species
from immich_dog_tagger.models import (
    Asset,
    Crop,
    CropClassification,
    Detection,
    Identity,
)
from immich_dog_tagger.services.friends_in_frame import (
    FriendsInFrameService,
    thumbnail_score,
)
from immich_dog_tagger.services.pet_occurrences import PetOccurrenceService


def _identity(
    session: Session, name: str, species=Species.DOG, active=True
) -> Identity:
    identity = Identity(name=name, species=species, is_active=active)
    session.add(identity)
    session.commit()
    return identity


def _asset(session: Session, key: str) -> Asset:
    asset = Asset(immich_asset_id=key, extension=".jpg")
    session.add(asset)
    session.flush()
    return asset


def _occurrence(
    session: Session,
    asset: Asset,
    identity: Identity,
    *,
    box=(0, 0, 300, 300),
    confidence=0.9,
    source=ClassificationSources.AUTO,
    not_animal=False,
    crop_species=None,
) -> int:
    detection = Detection(
        asset_id=asset.id,
        label=identity.species.value,
        confidence=confidence,
        x1=box[0],
        y1=box[1],
        x2=box[2],
        y2=box[3],
    )
    session.add(detection)
    session.flush()
    crop = Crop(
        detection_id=detection.id,
        path=f"{asset.id}-{identity.id}-{detection.id}.jpg",
        species=crop_species or identity.species,
        not_animal=not_animal,
    )
    session.add(crop)
    session.flush()
    classification = CropClassification(
        crop=crop, identity=identity.name, confidence=0.9, source=source
    )
    session.add(classification)
    session.commit()
    PetOccurrenceService(session).sync_classification(classification)
    session.commit()
    return crop.id


def test_thumbnail_score_prefers_square_large_confident_boxes():
    square = thumbnail_score(detection_confidence=0.9, x1=0, y1=0, x2=300, y2=300)
    thin = thumbnail_score(detection_confidence=0.9, x1=0, y1=0, x2=300, y2=100)
    tiny = thumbnail_score(detection_confidence=0.9, x1=0, y1=0, x2=40, y2=40)
    degenerate = thumbnail_score(detection_confidence=0.9, x1=5, y1=5, x2=5, y2=9)

    assert square > thin
    assert square > tiny
    assert degenerate == 0.0


def test_key_crop_prefers_human_confirmed_over_higher_scoring_auto(session):
    fibs = _identity(session, "Fibs")
    auto_id = _occurrence(session, _asset(session, "a"), fibs, confidence=0.99)
    reviewed_id = _occurrence(
        session,
        _asset(session, "b"),
        fibs,
        confidence=0.5,
        source=ClassificationSources.REVIEW,
    )

    key = FriendsInFrameService(session).key_crop_ids()

    assert key == {fibs.id: reviewed_id}
    assert auto_id != reviewed_id


def test_key_crop_prefers_square_large_confident_crop_within_a_tier(session):
    fibs = _identity(session, "Fibs")
    _occurrence(session, _asset(session, "a"), fibs, box=(0, 0, 400, 100))
    _occurrence(session, _asset(session, "b"), fibs, box=(0, 0, 60, 60))
    best = _occurrence(session, _asset(session, "c"), fibs, box=(0, 0, 320, 300))

    assert FriendsInFrameService(session).key_crop_ids()[fibs.id] == best


def test_key_crop_ties_break_on_lowest_crop_id(session):
    fibs = _identity(session, "Fibs")
    first = _occurrence(session, _asset(session, "a"), fibs)
    _occurrence(session, _asset(session, "b"), fibs)

    assert FriendsInFrameService(session).key_crop_ids()[fibs.id] == first


def test_key_crop_skips_not_animal_and_wrong_species_crops(session):
    fibs = _identity(session, "Fibs")
    _occurrence(session, _asset(session, "a"), fibs, not_animal=True)
    _occurrence(session, _asset(session, "b"), fibs, crop_species=Species.CAT)

    assert FriendsInFrameService(session).key_crop_ids() == {}


def test_build_empty_library(session):
    friends = FriendsInFrameService(session).build()

    assert friends.nodes == []
    assert friends.edges == []


def test_build_counts_shared_photos_once_even_with_duplicate_crops(session):
    fibs = _identity(session, "Fibs")
    henri = _identity(session, "Henri")
    shared = _asset(session, "shared")
    _occurrence(session, shared, fibs)
    _occurrence(session, shared, fibs)
    _occurrence(session, shared, henri)
    solo = _asset(session, "solo")
    _occurrence(session, solo, fibs)

    friends = FriendsInFrameService(session).build()
    counts = {node.name: node.image_count for node in friends.nodes}

    assert counts == {"Fibs": 2, "Henri": 1}
    assert [(e.a_id, e.b_id, e.count) for e in friends.edges] == [
        (fibs.id, henri.id, 1)
    ]


def test_build_keeps_pets_without_shared_photos_as_nodes(session):
    _identity(session, "Fibs")
    _identity(session, "Henri")

    friends = FriendsInFrameService(session).build()

    assert len(friends.nodes) == 2
    assert friends.edges == []
    assert all(node.key_crop_id is None for node in friends.nodes)


def test_build_pairs_cross_species_and_skips_inactive(session):
    fibs = _identity(session, "Fibs")
    mochi = _identity(session, "Mochi", species=Species.CAT)
    gone = _identity(session, "Gone", active=False)
    photo = _asset(session, "p")
    _occurrence(session, photo, fibs)
    _occurrence(session, photo, mochi)
    _occurrence(session, photo, gone)

    friends = FriendsInFrameService(session).build()

    assert {node.name for node in friends.nodes} == {"Fibs", "Mochi"}
    assert [(e.a_id, e.b_id) for e in friends.edges] == [(fibs.id, mochi.id)]


def test_build_orders_edges_strongest_first(session):
    a = _identity(session, "A")
    b = _identity(session, "B")
    c = _identity(session, "C")
    for key in ("1", "2"):
        photo = _asset(session, key)
        _occurrence(session, photo, b)
        _occurrence(session, photo, c)
    photo = _asset(session, "3")
    _occurrence(session, photo, a)
    _occurrence(session, photo, b)

    edges = FriendsInFrameService(session).build().edges

    assert [e.count for e in edges] == [2, 1]


def test_library_and_identities_returns_only_shared_photos(engine):
    from immich_dog_tagger.services.review_query import ReviewQueryService

    with Session(engine) as session:
        fibs = _identity(session, "Fibs")
        henri = _identity(session, "Henri")
        both = _asset(session, "both")
        only_fibs = _asset(session, "only-fibs")
        _occurrence(session, both, fibs)
        _occurrence(session, both, henri)
        _occurrence(session, only_fibs, fibs)

        service = ReviewQueryService(session)
        page = service.library(identity="Fibs", and_identities=["Henri"])

        assert page.total == 2
        assert {entry.item.prediction.identity for entry in page.items} == {
            "Fibs",
            "Henri",
        }
        assert {entry.item.immich_asset_id for entry in page.items} == {"both"}
        assert service.library(identity="Fibs").total == 2
