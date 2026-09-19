"""
Recomputes stored embedding vectors under the current embedding model.

Pairs with a model swap (ADR-010): an EmbeddingExample/CropClassification vector is only
meaningful compared against another vector from the same model, so replacing the embedder makes
every previously stored vector stale (and, since a new model's vectors are rarely even the same
length, incomparable rather than merely less accurate). This service recomputes each vector from
its source image on disk -- it never touches identity, confidence, source, or any other
label-bearing field, only the embedding vector and its `embedding_model` stamp, so it cannot
conflict with "reclassification never mutates reviewed labels" (ADR-009,
docs/ml-classification.md). `job_execution.py`'s REEMBED handler runs this and then a normal
Reclassify pass, so AUTO predictions catch up to the recomputed vectors afterward.

A crop whose cached file is missing on disk is skipped and counted, not treated as a fatal error
for the run -- the same isolate-and-continue treatment ClassificationService/ReclassifyService
give a missing crop file elsewhere in the pipeline (repairing it is
docs/specs/broken-crop-auto-repair.md's job, not this one's).
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from immich_dog_tagger.embedder import Embedder
from immich_dog_tagger.embeddings import embedding_to_blob
from immich_dog_tagger.models import CropClassification, EmbeddingExample

logger = logging.getLogger(__name__)

# Same chunk-and-commit shape as ClassificationService/ReclassifyService: bounds how long a
# single embed_batch() call runs uninterruptibly and how long state.db's write lock is held per
# commit, and gives should_cancel() a checkpoint between chunks.
BATCH_SIZE = 25


@dataclass
class ReembedSummary:
    examples_reembedded: int
    examples_skipped: int
    classifications_reembedded: int
    classifications_skipped: int


class ReembedService:
    def __init__(
        self,
        session: Session,
        embedder: Embedder,
        batch_size: int = BATCH_SIZE,
    ):
        self.session = session
        self.embedder = embedder
        self.batch_size = batch_size

    def reembed_all(
        self,
        should_cancel: Callable[[], bool] | None = None,
    ) -> ReembedSummary:
        examples_done, examples_skipped = self.reembed_examples(should_cancel)
        classifications_done, classifications_skipped = self.reembed_classifications(
            should_cancel
        )

        return ReembedSummary(
            examples_reembedded=examples_done,
            examples_skipped=examples_skipped,
            classifications_reembedded=classifications_done,
            classifications_skipped=classifications_skipped,
        )

    def reembed_examples(
        self,
        should_cancel: Callable[[], bool] | None = None,
    ) -> tuple[int, int]:
        """
        Recompute every EmbeddingExample.embedding from its crop_path. Never touches
        identity_id/source -- an example's identity is a human decision, its embedding is a
        derived representation of the same image.
        """
        done = 0
        skipped = 0
        last_id = 0

        while True:
            if should_cancel and should_cancel():
                break

            examples = (
                self.session.scalars(
                    select(EmbeddingExample)
                    .where(EmbeddingExample.id > last_id)
                    .order_by(EmbeddingExample.id)
                    .limit(self.batch_size)
                )
            ).all()

            if not examples:
                break

            last_id = examples[-1].id

            embeddable = []

            for example in examples:
                if Path(example.crop_path).exists():
                    embeddable.append(example)
                else:
                    skipped += 1
                    logger.warning(
                        "Reembed skipped example %d: missing crop file %s",
                        example.id,
                        example.crop_path,
                    )

            if embeddable:
                embeddings = self.embedder.embed_batch(
                    [Path(example.crop_path) for example in embeddable]
                )

                for example, embedding in zip(embeddable, embeddings, strict=True):
                    example.embedding = embedding_to_blob(embedding)
                    example.embedding_model = self.embedder.MODEL_ID
                    done += 1

            self.session.commit()

        logger.info(
            "Reembed examples: %d recomputed, %d skipped (missing crop file)",
            done,
            skipped,
        )

        return done, skipped

    def reembed_classifications(
        self,
        should_cancel: Callable[[], bool] | None = None,
    ) -> tuple[int, int]:
        """
        Recompute CropClassification.embedding for every crop that already has one. Only the
        vector and its embedding_model stamp change -- identity/confidence/source are left
        exactly as they are, whether AUTO, REVIEW, or MANUAL, so this can never overwrite a
        reviewed label.
        """
        done = 0
        skipped = 0
        last_id = 0

        while True:
            if should_cancel and should_cancel():
                break

            classifications = (
                self.session.scalars(
                    select(CropClassification)
                    .where(
                        CropClassification.id > last_id,
                        CropClassification.embedding.is_not(None),
                    )
                    .options(joinedload(CropClassification.crop))
                    .order_by(CropClassification.id)
                    .limit(self.batch_size)
                )
            ).all()

            if not classifications:
                break

            last_id = classifications[-1].id

            embeddable = []

            for classification in classifications:
                if Path(classification.crop.path).exists():
                    embeddable.append(classification)
                else:
                    skipped += 1
                    logger.warning(
                        "Reembed skipped classification %d: missing crop file %s",
                        classification.id,
                        classification.crop.path,
                    )

            if embeddable:
                embeddings = self.embedder.embed_batch(
                    [Path(classification.crop.path) for classification in embeddable]
                )

                for classification, embedding in zip(
                    embeddable, embeddings, strict=True
                ):
                    classification.embedding = embedding_to_blob(embedding)
                    classification.embedding_model = self.embedder.MODEL_ID
                    done += 1

            self.session.commit()

        logger.info(
            "Reembed classifications: %d recomputed, %d skipped (missing crop file)",
            done,
            skipped,
        )

        return done, skipped
