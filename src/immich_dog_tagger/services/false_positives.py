"""
"This is not a dog or cat" -- flagging a crop from the Photo Lookup page
(issue #185). Despite the name, this covers two legitimate reasons a
reviewer reaches for it (ADR-009): a literal YOLO false positive (no dog or
cat present at all), or a crop that does show a dog/cat the reviewer
doesn't recognize or doesn't want to assign an identity to. Both settle to
the same Unknown state below, so one flag serves both -- nothing downstream
distinguishes which reason applied.

Marking a crop settles its classification to Unknown through the same path
Review/Library corrections already use
(`ClassificationCorrectionService.correct()` with identity=None), not a
parallel implementation. That single call is what makes the mark actually
take effect everywhere an identity is read from: the crop drops out of the
active review queue (a ReviewAction is written), out of any Immich album on
the next sync (SyncService treats a None identity as Unknown, excluded by
the default sync policy), out of the owner's Insights for whatever identity
it used to carry (PetOccurrenceService clears the occurrence row), and out
of the reference set if this crop was ever learned as an example (the
learner forgets it) -- so a wrongly-tagged photo can't keep teaching the
classifier its own mistake. Marking only `Crop.not_animal` and leaving the
classification untouched was the original (issue #185) implementation; it
left Library showing "Confirmed as <Dog>" and sync still placing the photo
in that dog's album, which is the bug this fixes.

Unmarking only clears the flag -- it does not attempt to restore whatever
the classification predicted before the crop was marked. That prediction is
gone the moment it's settled to Unknown, same as undoing any other review
correction today: there's no "unsettle" primitive anywhere else in the app
either. The crop goes back to Unknown/reviewed, and the owner picks the
right identity (or leaves it Unknown) through the same identity control
Photo Lookup, Review and Library already share.
"""

from sqlalchemy.orm import Session

from immich_dog_tagger.enums import AssetStatus
from immich_dog_tagger.models import Crop
from immich_dog_tagger.services.correction import ClassificationCorrectionService


class FalsePositiveService:
    def __init__(
        self,
        session: Session,
        correction_service: ClassificationCorrectionService,
    ):
        self.session = session
        self.correction_service = correction_service

    def get_viewable(self, crop_id: int) -> Crop:
        """
        A crop fit to serve as an image: exists, and its source photo
        wasn't deleted in Immich and reconciled out (issue #194/FR-3). A
        removed asset's crop file may already be cleaned up, so treating it
        as not-found here keeps callers from serving a stale image or
        hitting an unhandled FileNotFoundError.
        """
        crop = self._get(crop_id)

        detection = crop.detection
        asset = detection.asset if detection is not None else None

        if asset is not None and asset.status == AssetStatus.REMOVED:
            raise ValueError(f"Crop {crop_id} not found")

        return crop

    def mark(self, crop_id: int) -> Crop:
        crop = self._get(crop_id)

        if not crop.not_animal:
            crop.not_animal = True

            if crop.classification is not None:
                # commit=False: the flag and the settled classification
                # land in one transaction, not two separate write-lock
                # acquisitions.
                self.correction_service.correct(
                    crop.classification.id,
                    None,
                    commit=False,
                )

            self.session.commit()

        return crop

    def unmark(self, crop_id: int) -> Crop:
        crop = self._get(crop_id)

        if crop.not_animal:
            crop.not_animal = False
            self.session.commit()

        return crop

    def _get(self, crop_id: int) -> Crop:
        crop = self.session.get(Crop, crop_id)

        if crop is None:
            raise ValueError(f"Crop {crop_id} not found")

        return crop
