import numpy as np

from sqlalchemy.orm import Session

from immich_dog_tagger.classifier import IdentityClassifier
from immich_dog_tagger.database import create_database
from immich_dog_tagger.embeddings import embedding_to_blob
from immich_dog_tagger.models import (
    Identity,
    EmbeddingExample,
)


def test_classifier_finds_closest_identity(tmp_path):

    engine = create_database(tmp_path)

    with Session(engine) as session:
        hermann = Identity(name="Hermann")

        session.add(hermann)
        session.flush()

        session.add(
            EmbeddingExample(
                identity_id=hermann.id,
                crop_path="hermann.jpg",
                embedding=embedding_to_blob(
                    np.array(
                        [1, 0, 0],
                        dtype=np.float32,
                    )
                ),
            )
        )

        session.commit()

        classifier = IdentityClassifier(session)

        result = classifier.classify(
            np.array(
                [0.9, 0.1, 0],
                dtype=np.float32,
            )
        )

        assert result.identity == "Hermann"
        assert result.confidence > 0.9
