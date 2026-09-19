"""
Embedding abstractions.
"""

from pathlib import Path
from typing import Protocol

import numpy as np

#: Stamped on EmbeddingExample/CropClassification rows written before `embedding_model` existed.
#: Every one of them was produced by the OpenCLIP embedder this project exclusively used until
#: ADR-010 replaced it, so the backfill migration (database.py) can name it precisely rather than
#: leaving it NULL/"unknown".
LEGACY_OPENCLIP_MODEL_ID = "openclip:ViT-B-32/laion2b_s34b_b79k"


class Embedder(Protocol):
    """
    Converts an image into an embedding vector.
    """

    #: Identifies the model that produces this embedder's vectors (stamped onto
    #: EmbeddingExample.embedding_model / CropClassification.embedding_model). A vector is only
    #: meaningful compared against another vector from the same model -- see ADR-010.
    MODEL_ID: str

    def embed(
        self,
        image_path: Path,
    ) -> np.ndarray:
        """
        Generate an embedding for an image.

        Returns:
            A 1-dimensional numpy array.
        """
        ...

    def embed_batch(
        self,
        image_paths: list[Path],
    ) -> np.ndarray:
        """
        Generate embeddings for a batch of images.

        Returns:
            A 2-dimensional numpy array, one row per input path, in order.
        """
        ...
