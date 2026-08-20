"""
Rescue a photo whose pet the detector missed (issue #147).

Nothing in the pipeline creates a crop outside YOLO detection, so a photo
detection found nothing in is invisible to everything downstream -- Review,
the Library, and the Immich albums -- permanently, and with no signal to
the owner that it happened. #146's coverage figures made the size of that
population visible; this makes it actionable.

The deliberate scope is the cheapest useful version: record that an asset
contains a pet, so the photo reaches that pet's album. It is not a manual
bounding-box editor, and it does not try to turn the photo into training
evidence -- see `ManualAssetTag` for why a synthetic detection/crop chain
would be the wrong shape.
"""

import logging
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session

from immich_dog_tagger.enums import Species
from immich_dog_tagger.models import (
    Asset,
    Detection,
    Identity,
    ManualAssetTag,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class UndetectedAsset:
    """A scanned photo that produced no crop, plus any manual tags on it."""

    asset_id: int
    immich_asset_id: str
    captured_at: datetime | None
    identities: list[str]


@dataclass(frozen=True)
class UndetectedAssetPage:
    items: list[UndetectedAsset]
    total: int
    limit: int
    offset: int


class ManualTagService:
    def __init__(self, session: Session):
        self.session = session

    def tag(
        self,
        asset_id: int,
        identity: str,
        species: Species,
    ) -> ManualAssetTag:
        """
        Record that this asset contains `identity`.

        Idempotent: tagging the same pet on the same asset twice is the
        same fact stated twice, and returns the existing row rather than
        raising or duplicating. That is what lets the owner re-tag without
        having to remember whether they already did, and what keeps a
        repeated request from multiplying album membership.
        """
        asset = self.session.get(Asset, asset_id)

        if asset is None:
            raise ValueError(f"Asset {asset_id} not found")

        pet = self.session.scalar(
            select(Identity).where(
                Identity.name == identity,
                Identity.species == species,
            )
        )

        if pet is None:
            raise ValueError(f"No {species.value} named {identity!r}")

        existing = self.session.scalar(
            select(ManualAssetTag).where(
                ManualAssetTag.asset_id == asset_id,
                ManualAssetTag.identity == identity,
                ManualAssetTag.species == species,
            )
        )

        if existing is not None:
            return existing

        tag = ManualAssetTag(
            asset_id=asset_id,
            identity=identity,
            species=species,
        )

        self.session.add(tag)
        self.session.commit()

        logger.info(
            "Asset %d manually tagged as %s %r",
            asset_id,
            species.value,
            identity,
        )

        return tag

    def untag(
        self,
        asset_id: int,
        identity: str,
        species: Species,
    ) -> bool:
        """
        Remove a manual tag. Reversible by design (ux-principles): a
        mistagged photo should be correctable without touching the
        database by hand, and the next sync removes it from the album via
        the existing stale-membership diff.
        """
        tag = self.session.scalar(
            select(ManualAssetTag).where(
                ManualAssetTag.asset_id == asset_id,
                ManualAssetTag.identity == identity,
                ManualAssetTag.species == species,
            )
        )

        if tag is None:
            return False

        self.session.delete(tag)
        self.session.commit()

        logger.info(
            "Manual tag removed from asset %d (%s %r)",
            asset_id,
            species.value,
            identity,
        )

        return True

    def tags_for(self, asset_id: int) -> list[ManualAssetTag]:
        return list(
            self.session.scalars(
                select(ManualAssetTag)
                .where(ManualAssetTag.asset_id == asset_id)
                .order_by(ManualAssetTag.identity)
            )
        )

    def undetected_assets(
        self,
        *,
        limit: int = 24,
        offset: int = 0,
        tagged: bool | None = None,
    ) -> UndetectedAssetPage:
        """
        Photos detection has finished with that produced no crop -- the
        population #146 counts, listed so it can be acted on.

        Scoped to the same statuses as #146's coverage denominator so the
        list and the number can never disagree: a photo still queued for
        detection has not been missed, it simply has not been looked at.

        `tagged` filters to photos already rescued (True) or still
        untouched (False); the default lists both.
        """
        from immich_dog_tagger.services.metrics import DETECTION_COMPLETE_STATUSES

        no_crops = ~exists(select(Detection.id).where(Detection.asset_id == Asset.id))

        has_tag = exists(
            select(ManualAssetTag.id).where(ManualAssetTag.asset_id == Asset.id)
        )

        conditions = [
            Asset.status.in_(DETECTION_COMPLETE_STATUSES),
            no_crops,
        ]

        if tagged is True:
            conditions.append(has_tag)
        elif tagged is False:
            conditions.append(~has_tag)

        total = self.session.scalar(
            select(func.count()).select_from(Asset).where(*conditions)
        )

        assets = list(
            self.session.scalars(
                select(Asset)
                .where(*conditions)
                # Newest first: a photo taken recently is the one the owner
                # is most likely to remember well enough to tag. The id
                # tiebreak keeps paging stable when capture dates are equal
                # or absent.
                .order_by(
                    Asset.captured_at.desc().nullslast(),
                    Asset.id.desc(),
                )
                .limit(limit)
                .offset(offset)
            )
        )

        # One query for every listed asset's tags rather than one per
        # asset -- the N+1 shape this codebase has had to fix repeatedly.
        tags_by_asset: dict[int, list[str]] = {}

        if assets:
            rows = self.session.execute(
                select(ManualAssetTag.asset_id, ManualAssetTag.identity)
                .where(ManualAssetTag.asset_id.in_([a.id for a in assets]))
                .order_by(ManualAssetTag.identity)
            ).all()

            for tagged_asset_id, identity in rows:
                tags_by_asset.setdefault(tagged_asset_id, []).append(identity)

        return UndetectedAssetPage(
            items=[
                UndetectedAsset(
                    asset_id=asset.id,
                    immich_asset_id=asset.immich_asset_id,
                    captured_at=asset.captured_at,
                    identities=tags_by_asset.get(asset.id, []),
                )
                for asset in assets
            ],
            total=total or 0,
            limit=limit,
            offset=offset,
        )
