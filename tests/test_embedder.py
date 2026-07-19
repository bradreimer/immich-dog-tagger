import numpy as np

from immich_dog_tagger.embedder import Embedder


def test_embedder_protocol_exists():
    """
    Ensure the embedding interface is importable.

    Concrete implementations are tested separately.
    """

    assert Embedder is not None