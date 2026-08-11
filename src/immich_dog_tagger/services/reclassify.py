"""
Reclassification service.

Recomputes AUTO predictions from the current labeled-example set. Unlike
the pipeline's classify stage, Reclassify:

- never touches crops whose current classification came from a human
  (source REVIEW/MANUAL) -- those are ground truth, not derived state.
- reuses a crop's cached embedding when one is already stored, instead of
  recomputing it from the image file.
- runs as a versioned, auditable ClassificationPass rather than mutating
  rows with no record of when/why they changed.
- terminates cleanly (rather than mass-unknowning every crop) when there
  are no labeled examples to classify against.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from immich_dog_tagger.classifier import IdentityClassifier
from immich_dog_tagger.embeddings import blob_to_embedding, embedding_to_blob
from immich_dog_tagger.enums import ClassificationPassStatus, ClassificationSources
from immich_dog_tagger.models import (
    ClassificationPass,
    CropClassification,
    EmbeddingExample,
    Identity,
)
from immich_dog_tagger.openclip_embedder import OpenClipEmbedder
from immich_dog_tagger.policy import (
    DEFAULT_POLICY,
    ClassificationDecision,
    ClassifierPolicy,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ReclassifyResult:
    pass_id: int
    status: ClassificationPassStatus
    eligible_count: int
    confident_count: int
    needs_review_count: int
    unknown_count: int
    changed_count: int
    message: str


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class ReclassifyService:
    def __init__(
        self,
        session: Session,
        embedder: OpenClipEmbedder,
        policy: ClassifierPolicy = DEFAULT_POLICY,
        batch_size: int = 200,
    ):
        self.session = session
        self.embedder = embedder
        self.policy = policy
        self.batch_size = batch_size

    def reclassify(self, progress=None) -> ReclassifyResult:
        classification_pass = ClassificationPass(
            status=ClassificationPassStatus.RUNNING,
            classifier_version=self.policy.version,
            threshold=self.policy.confident_threshold,
        )
        self.session.add(classification_pass)
        self.session.commit()
        self.session.refresh(classification_pass)

        logger.info(
            "Reclassify pass %d started (classifier_version=%s threshold=%.2f)",
            classification_pass.id,
            self.policy.version,
            self.policy.confident_threshold,
        )

        try:
            message = self._run(classification_pass, progress)
        except Exception as exc:
            self.session.rollback()

            classification_pass.status = ClassificationPassStatus.FAILED
            classification_pass.error_message = str(exc) or exc.__class__.__name__
            classification_pass.completed_at = _now()

            self.session.add(classification_pass)
            self.session.commit()

            logger.exception(
                "Reclassify pass %d failed after %d/%d crop(s)",
                classification_pass.id,
                classification_pass.confident_count
                + classification_pass.needs_review_count
                + classification_pass.unknown_count,
                classification_pass.eligible_count,
            )
            raise

        classification_pass.status = ClassificationPassStatus.COMPLETED
        classification_pass.completed_at = _now()
        self.session.commit()
        self.session.refresh(classification_pass)

        logger.info(
            "Reclassify pass %d completed: eligible=%d confident=%d needs_review=%d "
            "unknown=%d changed=%d",
            classification_pass.id,
            classification_pass.eligible_count,
            classification_pass.confident_count,
            classification_pass.needs_review_count,
            classification_pass.unknown_count,
            classification_pass.changed_count,
        )

        return ReclassifyResult(
            pass_id=classification_pass.id,
            status=classification_pass.status,
            eligible_count=classification_pass.eligible_count,
            confident_count=classification_pass.confident_count,
            needs_review_count=classification_pass.needs_review_count,
            unknown_count=classification_pass.unknown_count,
            changed_count=classification_pass.changed_count,
            message=message,
        )

    def _run(
        self,
        classification_pass: ClassificationPass,
        progress,
    ) -> str:
        example_count = (
            self.session.scalar(
                select(func.count())
                .select_from(EmbeddingExample)
                .join(Identity)
                .where(Identity.is_active.is_(True))
            )
            or 0
        )

        eligible_ids = self.session.scalars(
            select(CropClassification.id)
            .where(CropClassification.source == ClassificationSources.AUTO)
            .order_by(CropClassification.id)
        ).all()

        classification_pass.eligible_count = len(eligible_ids)
        self.session.commit()

        if example_count == 0:
            message = "No labeled examples available; nothing to reclassify."

            if progress:
                progress.message(message)

            return message

        if not eligible_ids:
            message = "No eligible crops to reclassify."

            if progress:
                progress.message(message)

            return message

        classifier = IdentityClassifier(self.session, policy=self.policy)

        confident = needs_review = unknown = changed = 0
        processed = 0
        total = len(eligible_ids)

        if progress:
            progress.set(current=0, total=total, message="Reclassifying crops")

        for start in range(0, total, self.batch_size):
            chunk_ids = eligible_ids[start : start + self.batch_size]

            classifications = self.session.scalars(
                select(CropClassification)
                .where(CropClassification.id.in_(chunk_ids))
                .order_by(CropClassification.id)
            ).all()

            missing_embedding = [c for c in classifications if c.embedding is None]

            if missing_embedding:
                embeddings = self.embedder.embed_batch(
                    [Path(c.crop.path) for c in missing_embedding]
                )

                for classification, embedding in zip(
                    missing_embedding, embeddings, strict=True
                ):
                    classification.embedding = embedding_to_blob(embedding)

            for classification in classifications:
                embedding = blob_to_embedding(classification.embedding)
                result = classifier.classify(embedding)

                if result.identity != classification.identity:
                    changed += 1

                classification.identity = result.identity
                classification.confidence = result.similarity
                classification.matched_example_id = result.matched_example_id
                classification.candidates = [
                    {
                        "identity": candidate.identity,
                        "similarity": candidate.similarity,
                        "matched_example_id": candidate.matched_example_id,
                    }
                    for candidate in result.candidates
                ]
                classification.classifier_version = self.policy.version
                classification.classification_pass_id = classification_pass.id

                decision = self.policy.decide(
                    identity=classification.identity,
                    similarity=classification.confidence,
                )

                if decision is ClassificationDecision.CONFIDENT:
                    confident += 1
                elif decision is ClassificationDecision.NEEDS_REVIEW:
                    needs_review += 1
                else:
                    unknown += 1

            processed += len(classifications)

            classification_pass.confident_count = confident
            classification_pass.needs_review_count = needs_review
            classification_pass.unknown_count = unknown
            classification_pass.changed_count = changed

            self.session.commit()

            if progress:
                progress.set(
                    current=processed,
                    total=total,
                    message=f"Reclassified {processed}/{total} crop(s)",
                )

        return f"Reclassified {total} crop(s)."
