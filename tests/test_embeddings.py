import numpy as np

from immich_dog_tagger.embeddings import (
    embedding_to_blob,
    blob_to_embedding,
)


def test_embedding_round_trip():

    original = np.array(
        [
            0.1,
            0.2,
            0.3,
        ],
        dtype=np.float32,
    )

    blob = embedding_to_blob(original)

    restored = blob_to_embedding(blob)

    assert np.array_equal(
        original,
        restored,
    )
