"""
Utilities for storing and loading embeddings.
"""

import numpy as np


def embedding_to_blob(
    embedding: np.ndarray,
) -> bytes:
    """
    Convert an embedding vector into SQLite storage format.
    """

    return embedding.astype(np.float32).tobytes()


def blob_to_embedding(
    blob: bytes,
) -> np.ndarray:
    """
    Restore an embedding vector from SQLite storage.
    """

    return np.frombuffer(
        blob,
        dtype=np.float32,
    )
