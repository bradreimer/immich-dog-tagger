"""
Services for creating identity examples.
"""

from pathlib import Path

from sqlalchemy.orm import Session

from immich_dog_tagger.models import (
    Identity,
    EmbeddingExample,
)
from immich_dog_tagger.embedder import Embedder
from immich_dog_tagger.embeddings import embedding_to_blob


class Learner:
    def __init__(
        self,
        embedder: Embedder,
        session: Session,
    ):
        self.embedder = embedder
        self.session = session

    def learn(
        self,
        identity_name: str,
        image_dir: Path,
        *,
        source: str = "manual",
    ) -> int:
        identity = (
            self.session.query(Identity).filter_by(name=identity_name).one_or_none()
        )

        if identity is None:
            identity = Identity(name=identity_name)

            self.session.add(identity)

            self.session.flush()

        count = 0

        for image_path in sorted(image_dir.iterdir()):
            if not image_path.is_file():
                continue

            existing = (
                self.session.query(EmbeddingExample)
                .filter_by(
                    identity_id=identity.id,
                    crop_path=str(image_path),
                )
                .one_or_none()
            )

            if existing is not None:
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

        return count
