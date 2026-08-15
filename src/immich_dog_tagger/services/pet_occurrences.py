"""
Materializes PetOccurrence rows from settled classification state.

PetOccurrence is a derived fact, not a new source of truth (ADR-004): every
row here is rebuildable at any time from CropClassification + Identity, and
this service is the only writer of the table.
"""

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from immich_dog_tagger.models import (
    Crop,
    CropClassification,
    Detection,
    Identity,
    PetOccurrence,
)

logger = logging.getLogger(__name__)

UNKNOWN_IDENTITY = "Unknown"


class PetOccurrenceService:
    def __init__(self, session: Session):
        self.session = session

    def sync_classification(self, classification: CropClassification) -> None:
        """
        Bring the PetOccurrence for one classification in line with its
        current identity/confidence/source. Called wherever a
        classification's identity is settled: auto-classification, review
        correction, and reclassification.
        """

        existing = self.session.scalar(
            select(PetOccurrence).where(
                PetOccurrence.crop_classification_id == classification.id
            )
        )

        if (
            classification.identity is None
            or classification.identity == UNKNOWN_IDENTITY
        ):
            if existing is not None:
                self.session.delete(existing)

            return

        crop = classification.crop
        detection = crop.detection if crop is not None else None
        asset = detection.asset if detection is not None else None

        if crop is None or asset is None:
            # No asset context to attach an occurrence to -- fail open
            # (skip) rather than raise; this can only happen for crops that
            # predate a detection/asset relationship, which sync_all()'s
            # rebuild will simply leave unmaterialized.
            return

        identity = self.session.scalar(
            select(Identity).where(
                Identity.species == crop.species,
                Identity.name == classification.identity,
            )
        )

        if identity is None:
            # The classifier/reviewer named an identity that isn't a
            # registered Identity row -- shouldn't happen in normal
            # operation, but fail open rather than raise mid-pipeline.
            logger.warning(
                "PetOccurrence sync: no Identity row for %r (species=%s), skipping",
                classification.identity,
                crop.species,
            )
            return

        if existing is not None:
            existing.asset_id = asset.id
            existing.identity_id = identity.id
            existing.confidence = classification.confidence
            existing.source = classification.source
        else:
            self.session.add(
                PetOccurrence(
                    classification=classification,
                    asset_id=asset.id,
                    identity_id=identity.id,
                    confidence=classification.confidence,
                    source=classification.source,
                )
            )

    def sync_all(self, batch_size: int = 500) -> int:
        """
        Rebuild every PetOccurrence from current classification state.
        For backfilling a library with classification history that
        predates this feature. Returns the number of classifications
        processed.
        """

        classification_ids = self.session.scalars(
            select(CropClassification.id).order_by(CropClassification.id)
        ).all()

        processed = 0

        for start in range(0, len(classification_ids), batch_size):
            chunk_ids = classification_ids[start : start + batch_size]

            classifications = self.session.scalars(
                select(CropClassification)
                .where(CropClassification.id.in_(chunk_ids))
                .options(
                    selectinload(CropClassification.crop)
                    .selectinload(Crop.detection)
                    .selectinload(Detection.asset)
                )
            ).all()

            for classification in classifications:
                self.sync_classification(classification)
                processed += 1

            self.session.commit()

        logger.info("PetOccurrence backfill: processed %d classification(s)", processed)

        return processed
