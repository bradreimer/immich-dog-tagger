"""
Embedding abstractions.
"""

from pathlib import Path
from typing import Protocol

import numpy as np


class Embedder(Protocol):
    """
    Converts an image into an embedding vector.
    """

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