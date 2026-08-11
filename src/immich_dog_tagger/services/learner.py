"""
Services for creating identity examples.
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from immich_dog_tagger.embedder import Embedder
from immich_dog_tagger.embeddings import embedding_to_blob
from immich_dog_tagger.media import is_supported_image
from immich_dog_tagger.models import EmbeddingExample, EmbeddingSources, Identity


@dataclass
class LearnSummary:
    imported: int
    skipped_existing: int


class Learner:
    def __init__(
        self,
        embedder: Embedder,
        session: Session,
    ):
        self.embedder = embedder
        self.session = session

    def learn_image(
        self,
        identity_name: str,
        image_path: Path,
        *,
        source: EmbeddingSources = EmbeddingSources.BOOTSTRAP,
        captured_at: datetime | None = None,
    ) -> bool:
        """
        Upsert a single reference example for `identity_name` at `image_path`.

        A physical crop can only depict one dog, so any existing example for
        this same path under a *different* identity is superseded (deleted)
        first. This keeps re-reviewing an item idempotent: correcting a crop
        from "Fibs" to "Hermann" removes the stale Fibs example instead of
        leaving it behind to pollute future classifications. Caller is
        responsible for committing.
        """
        identity = self._get_or_create_identity(identity_name)

        self._forget_other_identities(identity.id, image_path)

        existing = self._find_example(identity.id, image_path)

        if existing is not None:
            return False

        embedding = self.embedder.embed(image_path)

        example = EmbeddingExample(
            identity_id=identity.id,
            crop_path=str(image_path),
            embedding=embedding_to_blob(embedding),
            source=source,
            captured_at=captured_at,
        )

        self.session.add(example)

        return True

    def forget_image(
        self,
        image_path: Path,
    ) -> int:
        """
        Remove every reference example for `image_path`, regardless of
        identity. Used when a review corrects a crop to Unknown: it should
        stop serving as a reference example for whatever identity it was
        previously attributed to. Caller is responsible for committing.
        """
        examples = self.session.scalars(
            select(EmbeddingExample).where(
                EmbeddingExample.crop_path == str(image_path),
            )
        ).all()

        for example in examples:
            self.session.delete(example)

        return len(examples)

    def learn(
        self,
        identity_name: str,
        image_dir: Path,
        *,
        source: EmbeddingSources = EmbeddingSources.BOOTSTRAP,
        captured_at: datetime | None = None,
    ) -> LearnSummary:
        identity = self._get_or_create_identity(identity_name)

        count = 0
        skipped_existing = 0

        for image_path in sorted(image_dir.iterdir()):
            if not image_path.is_file():
                continue

            if not is_supported_image(image_path):
                continue

            self._forget_other_identities(identity.id, image_path)

            existing = self._find_example(identity.id, image_path)

            if existing is not None:
                skipped_existing += 1
                continue

            embedding = self.embedder.embed(image_path)

            example = EmbeddingExample(
                identity_id=identity.id,
                crop_path=str(image_path),
                embedding=embedding_to_blob(embedding),
                source=source,
                captured_at=captured_at,
            )

            self.session.add(example)

            count += 1

        self.session.commit()

        return LearnSummary(
            imported=count,
            skipped_existing=skipped_existing,
        )

    def _get_or_create_identity(
        self,
        identity_name: str,
    ) -> Identity:
        identity = self.session.scalar(
            select(Identity).where(Identity.name == identity_name)
        )

        if identity is None:
            identity = Identity(name=identity_name)

            self.session.add(identity)
            self.session.flush()

        return identity

    def _find_example(
        self,
        identity_id: int,
        image_path: Path,
    ) -> EmbeddingExample | None:
        return self.session.scalar(
            select(EmbeddingExample).where(
                EmbeddingExample.identity_id == identity_id,
                EmbeddingExample.crop_path == str(image_path),
            )
        )

    def _forget_other_identities(
        self,
        identity_id: int,
        image_path: Path,
    ) -> None:
        stale_examples = self.session.scalars(
            select(EmbeddingExample).where(
                EmbeddingExample.crop_path == str(image_path),
                EmbeddingExample.identity_id != identity_id,
            )
        ).all()

        for example in stale_examples:
            self.session.delete(example)
