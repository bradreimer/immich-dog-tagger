"""
Library-wide pet co-occurrence ("Friends in Frame") and per-pet key thumbnails.

Everything here is derived at read time from PetOccurrence (ADR-004) -- no
stored conclusion, no schema. See docs/specs/friends-in-frame.md.
"""

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session, aliased

from immich_dog_tagger.enums import ClassificationSources, Species
from immich_dog_tagger.models import (
    Crop,
    CropClassification,
    Detection,
    Identity,
    PetOccurrence,
)

# A crop at least this many pixels on its short side is "big enough" for a
# thumbnail; smaller ones are down-weighted proportionally.
FULL_SIZE_SHORT_SIDE = 256


@dataclass(frozen=True)
class FriendNode:
    id: int
    name: str
    species: Species
    image_count: int
    key_crop_id: int | None


@dataclass(frozen=True)
class FriendEdge:
    a_id: int
    b_id: int
    count: int


@dataclass(frozen=True)
class FriendsInFrame:
    nodes: list[FriendNode]
    edges: list[FriendEdge]


def thumbnail_score(
    *, detection_confidence: float, x1: int, y1: int, x2: int, y2: int
) -> float:
    """
    How well a crop works as a circular pet avatar: the detector's confidence
    (the clarity signal Top Photos already uses) x how square the box is (a
    square fits a circle without cutting the animal) x how large it is.
    """
    width = x2 - x1
    height = y2 - y1
    short_side = min(width, height)
    long_side = max(width, height)

    if short_side <= 0:
        return 0.0

    squareness = short_side / long_side
    size_factor = min(1.0, short_side / FULL_SIZE_SHORT_SIDE)

    return detection_confidence * squareness * size_factor


class FriendsInFrameService:
    def __init__(self, session: Session):
        self.session = session

    def key_crop_ids(self, identity_ids: list[int] | None = None) -> dict[int, int]:
        """
        One crop id per identity: human-confirmed occurrences first (so a
        classifier mistake is never promoted to a pet's face), then the best
        `thumbnail_score`, ties on the lowest crop id. Identities with no
        eligible crop are absent.
        """
        query = (
            select(
                PetOccurrence.identity_id,
                PetOccurrence.source,
                Crop.id,
                Detection.confidence,
                Detection.x1,
                Detection.y1,
                Detection.x2,
                Detection.y2,
            )
            .select_from(PetOccurrence)
            .join(
                CropClassification,
                PetOccurrence.crop_classification_id == CropClassification.id,
            )
            .join(Crop, CropClassification.crop_id == Crop.id)
            .join(Detection, Crop.detection_id == Detection.id)
            .join(Identity, PetOccurrence.identity_id == Identity.id)
            .where(Crop.not_animal.is_(False), Crop.species == Identity.species)
        )

        if identity_ids is not None:
            query = query.where(PetOccurrence.identity_id.in_(identity_ids))

        best: dict[int, tuple[tuple[int, float, int], int]] = {}

        for (
            identity_id,
            source,
            crop_id,
            confidence,
            x1,
            y1,
            x2,
            y2,
        ) in self.session.execute(query).yield_per(1000):
            rank = (
                0 if source == ClassificationSources.AUTO else 1,
                thumbnail_score(
                    detection_confidence=confidence, x1=x1, y1=y1, x2=x2, y2=y2
                ),
                -crop_id,
            )
            current = best.get(identity_id)

            if current is None or rank > current[0]:
                best[identity_id] = (rank, crop_id)

        return {identity_id: crop_id for identity_id, (_, crop_id) in best.items()}

    def build(self) -> FriendsInFrame:
        identities = self.session.scalars(
            select(Identity)
            .where(Identity.is_active.is_(True))
            .order_by(Identity.species.asc(), Identity.name.asc())
        ).all()

        if not identities:
            return FriendsInFrame(nodes=[], edges=[])

        active_ids = {identity.id for identity in identities}

        image_counts = dict(
            self.session.execute(
                select(
                    PetOccurrence.identity_id,
                    func.count(func.distinct(PetOccurrence.asset_id)),
                ).group_by(PetOccurrence.identity_id)
            ).all()
        )
        key_crops = self.key_crop_ids(list(active_ids))

        left = aliased(PetOccurrence)
        right = aliased(PetOccurrence)
        pair_rows = self.session.execute(
            select(
                left.identity_id,
                right.identity_id,
                func.count(func.distinct(left.asset_id)),
            )
            .select_from(left)
            .join(
                right,
                (left.asset_id == right.asset_id)
                & (left.identity_id < right.identity_id),
            )
            .group_by(left.identity_id, right.identity_id)
        ).all()

        nodes = [
            FriendNode(
                id=identity.id,
                name=identity.name,
                species=identity.species,
                image_count=image_counts.get(identity.id, 0),
                key_crop_id=key_crops.get(identity.id),
            )
            for identity in identities
        ]
        edges = [
            FriendEdge(a_id=a_id, b_id=b_id, count=count)
            for a_id, b_id, count in pair_rows
            if a_id in active_ids and b_id in active_ids
        ]
        edges.sort(key=lambda edge: (-edge.count, edge.a_id, edge.b_id))

        return FriendsInFrame(nodes=nodes, edges=edges)
