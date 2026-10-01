"""
OpenCLIP image embedding implementation.

Restored as the active embedder by ADR-011 after MegaDescriptor (ADR-010) proved unable to match
the same dog across different days on a real pet library.
"""

from pathlib import Path

import numpy as np
import open_clip
import torch

from .embedder import LEGACY_OPENCLIP_MODEL_ID
from .images import open_upright


class OpenClipEmbedder:
    #: The same id the ADR-010 backfill stamped on pre-MegaDescriptor rows, so vectors that were
    #: never re-embedded stay directly comparable with new ones.
    MODEL_ID = LEGACY_OPENCLIP_MODEL_ID

    def __init__(
        self,
        model_name: str = "ViT-B-32",
        pretrained: str = "laion2b_s34b_b79k",
    ):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        self.model, _, self.preprocess = open_clip.create_model_and_transforms(
            model_name,
            pretrained=pretrained,
        )

        self.model.to(self.device)

        self.model.eval()

    def embed(
        self,
        image_path: Path,
    ) -> np.ndarray:

        image = open_upright(image_path).convert("RGB")

        tensor = self.preprocess(image).unsqueeze(0).to(self.device)

        with torch.no_grad():
            features = self.model.encode_image(tensor)

        features = features / features.norm(
            dim=-1,
            keepdim=True,
        )

        return features[0].cpu().numpy().astype(np.float32)

    def embed_batch(
        self,
        image_paths: list[Path],
    ) -> np.ndarray:
        images = [
            self.preprocess(open_upright(path).convert("RGB")) for path in image_paths
        ]

        tensor = torch.stack(images).to(self.device)

        with torch.no_grad():
            features = self.model.encode_image(tensor)

        features = features / features.norm(
            dim=-1,
            keepdim=True,
        )

        return features.cpu().numpy().astype(np.float32)
