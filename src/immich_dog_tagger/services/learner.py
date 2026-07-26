"""
Services for creating identity examples.
"""

from pathlib import Path
from dataclasses import dataclass
from sqlalchemy.orm import Session
from sqlalchemy import select

from immich_dog_tagger.embedder import Embedder
from immich_dog_tagger.embeddings import embedding_to_blob
from immich_dog_tagger.media import is_supported_image
from immich_dog_tagger.models import Identity, EmbeddingExample, EmbeddingSources


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
    ) -> bool:
        identity = self.session.scalar(
            select(Identity).where(Identity.name == identity_name)
        )

        if identity is None:
            identity = Identity(name=identity_name)

            self.session.add(identity)
            self.session.flush()

        existing = self.session.scalar(
            select(EmbeddingExample).where(
                EmbeddingExample.identity_id == identity.id,
                EmbeddingExample.crop_path == str(image_path),
            )
        )

        if existing is not None:
            return False

        embedding = self.embedder.embed(image_path)

        example = EmbeddingExample(
            identity_id=identity.id,
            crop_path=str(image_path),
            embedding=embedding_to_blob(embedding),
            source=source,
        )

        self.session.add(example)

        return True

    def learn(
        self,
        identity_name: str,
        image_dir: Path,
        *,
        source: EmbeddingSources = EmbeddingSources.BOOTSTRAP,
    ) -> LearnSummary:
        identity = self.session.scalar(
            select(Identity).where(Identity.name == identity_name)
        )

        if identity is None:
            identity = Identity(name=identity_name)

            self.session.add(identity)

            self.session.flush()

        count = 0
        skipped_existing = 0

        for image_path in sorted(image_dir.iterdir()):
            if not image_path.is_file():
                continue

            if not is_supported_image(image_path):
                continue

            existing = self.session.scalar(
                select(EmbeddingExample).where(
                    EmbeddingExample.identity_id == identity.id,
                    EmbeddingExample.crop_path == str(image_path),
                )
            )

            if existing is not None:
                skipped_existing += 1
                continue

            embedding = self.embedder.embed(image_path)

            example = EmbeddingExample(
                identity_id=identity.id,
                crop_path=str(image_path),
                embedding=embedding_to_blob(embedding),
                source=source,
            )

            self.session.add(example)

            count += 1

        self.session.commit()

        return LearnSummary(
            imported=count,
            skipped_existing=skipped_existing,
        )
