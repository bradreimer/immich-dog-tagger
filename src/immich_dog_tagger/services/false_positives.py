"""
"This is not a dog or cat" -- flagging a YOLO false positive from the Photo
Lookup page (issue #185).

Deliberately narrow: this only records the fact on the crop (`Crop.not_animal`,
mirroring how `species` already lives there). It does not touch the crop's
classification, does not affect the review queue, and is not fed back into
the classifier or the learner -- none of that was asked for, and each is a
larger decision (e.g. whether a flagged crop should still count toward
review-queue totals) better made once there's a second place in the app that
needs this signal. Reversible by design: marking is a toggle, not a delete,
per the app's "prefer reversible over destructive" UX principle.
"""

from sqlalchemy.orm import Session

from immich_dog_tagger.models import Crop


class FalsePositiveService:
    def __init__(self, session: Session):
        self.session = session

    def mark(self, crop_id: int) -> Crop:
        return self._set(crop_id, True)

    def unmark(self, crop_id: int) -> Crop:
        return self._set(crop_id, False)

    def _set(self, crop_id: int, not_animal: bool) -> Crop:
        crop = self.session.get(Crop, crop_id)

        if crop is None:
            raise ValueError(f"Crop {crop_id} not found")

        if crop.not_animal != not_animal:
            crop.not_animal = not_animal
            self.session.commit()

        return crop
