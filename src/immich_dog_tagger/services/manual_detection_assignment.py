"""
Manually map a crop-less or mislabeled detection to a dog/cat (issue #261).

A `Detection` only ever gets a `Crop` -- and therefore anything to classify
-- when its raw YOLO `label` is already `dog` or `cat` (`CropWriter.
_DETECTABLE_LABELS`). A detection YOLO labeled something else entirely
(`person`, `sheep`, any other COCO class) never becomes a crop, even when
the box is genuinely a dog or cat the detector misclassified. Before this,
that was a permanent dead end: nothing in the app could create a crop for
such a detection, so there was no species/identity control to correct it
with. See `docs/specs/photo-lookup.md`'s "manually map a crop-less or
mislabeled detection" addendum for the full design rationale, including why
this deliberately does not depend on `ClassificationService`/
`IdentityClassifier` automatic inference (the #245/#249/#253/#256 history:
an automatic "classify a pending detection" feature shipped, was found
non-functional in production, and was fully reverted).

Both entry points here create the crop the same way -- download the
original live from Immich (the pipeline's local cached copy is long gone by
the time a human notices this in review, per
`docs/specs/storage-lifecycle-cleanup.md`), crop the detection's stored box
out of it via `CropWriter.crop_one()` (the same padding/orientation logic
the normal pipeline crop stage uses) -- and then hand off to the existing
human-decision write paths rather than duplicating their logic:
`ClassificationCorrectionService.correct()` for an identity (real name or
Unknown), or `FalsePositiveService.mark()` for "not a dog or cat". Neither
of those paths is touched or reimplemented; this only ever supplies them
with a crop/classification that didn't exist yet.
"""

import io
import logging
from pathlib import Path

from sqlalchemy.orm import Session

from immich_dog_tagger.crops import CropWriter
from immich_dog_tagger.embedder import Embedder
from immich_dog_tagger.embeddings import embedding_to_blob
from immich_dog_tagger.enums import ClassificationSources, Species
from immich_dog_tagger.images import open_upright, upright_size
from immich_dog_tagger.immich import ImmichClient
from immich_dog_tagger.models import Crop, CropClassification, Detection
from immich_dog_tagger.services.correction import ClassificationCorrectionService
from immich_dog_tagger.services.false_positives import FalsePositiveService

logger = logging.getLogger(__name__)


class ManualDetectionAssignmentService:
    def __init__(
        self,
        session: Session,
        client: ImmichClient,
        embedder: Embedder,
        crop_writer: CropWriter,
        correction_service: ClassificationCorrectionService,
        false_positive_service: FalsePositiveService,
    ):
        self.session = session
        self.client = client
        self.embedder = embedder
        self.crop_writer = crop_writer
        self.correction_service = correction_service
        self.false_positive_service = false_positive_service

    def assign(
        self,
        detection_id: int,
        species: Species,
        identity: str | None,
    ) -> Crop:
        """
        Map a crop-less detection to `species`, optionally naming an
        identity (or `None`, landing at Unknown -- "confirm the species,
        decide the identity later"). Delegates the identity decision itself
        to `ClassificationCorrectionService.correct()`, the exact write path
        every other human identity decision in the app already goes
        through, so this crop is indistinguishable afterward from an
        ordinary reviewed one: 100% confidence, a `ReviewAction`, a learner
        reference example when named, and an Insights occurrence sync.
        """
        crop = self._create_crop(detection_id, species)

        # A placeholder the immediately-following correct() call settles for
        # real (confidence, source, identity) -- created first only because
        # correct() needs an existing classification_id to operate on.
        classification = CropClassification(
            crop=crop,
            identity=None,
            confidence=-1.0,
            candidates=[],
            source=ClassificationSources.MANUAL,
        )
        self.session.add(classification)
        self.session.flush()

        classification.embedding = embedding_to_blob(
            self.embedder.embed(Path(crop.path))
        )

        self.correction_service.correct(classification.id, identity)

        logger.info(
            "Detection %d manually mapped to species=%s identity=%r (crop %d)",
            detection_id,
            species.value,
            identity,
            crop.id,
        )

        return crop

    def mark_not_animal(self, detection_id: int) -> Crop:
        """
        Create a crop-less detection's crop and immediately flag it "not a
        dog or cat" -- confirming the detector was right not to treat this
        box as one, or that a reviewer doesn't want to name it. Species is
        arbitrary here (the model's own default): per ADR-009, nothing
        downstream reads a not-animal crop's species for anything.
        """
        crop = self._create_crop(detection_id, Species.DOG)

        self.false_positive_service.mark(crop.id)

        logger.info(
            "Detection %d manually marked not a dog or cat (crop %d)",
            detection_id,
            crop.id,
        )

        return crop

    def _create_crop(self, detection_id: int, species: Species) -> Crop:
        detection = self.session.get(Detection, detection_id)

        if detection is None:
            raise ValueError(f"Detection {detection_id} not found")

        if detection.crop is not None:
            raise ValueError(
                f"Detection {detection_id} already has a crop; use the "
                "existing species/identity correction controls instead"
            )

        asset = detection.asset

        content = self.client.download_asset(asset.immich_asset_id)
        expected_size = upright_size(
            asset.exif_width, asset.exif_height, asset.exif_orientation
        )
        image = open_upright(io.BytesIO(content), expected_size).convert("RGB")

        cropped = self.crop_writer.crop_one(
            image,
            detection.x1,
            detection.y1,
            detection.x2,
            detection.y2,
            context=f"asset={asset.immich_asset_id} detection={detection_id} (manual)",
        )

        if cropped is None:
            raise ValueError(
                f"Detection {detection_id}'s box is degenerate; cannot create a crop"
            )

        self.crop_writer.crop_dir.mkdir(parents=True, exist_ok=True)

        output_path = (
            self.crop_writer.crop_dir / f"{asset.id}_manual_{detection.id}.jpg"
        )

        cropped.save(output_path)

        crop = Crop(
            detection=detection,
            path=str(output_path),
            species=species,
        )
        self.session.add(crop)
        self.session.flush()

        return crop
