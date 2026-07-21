"""
OpenCLIP image embedding implementation.
"""

from pathlib import Path

import numpy as np
import torch
import open_clip
from PIL import Image


class OpenClipEmbedder:
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

        image = Image.open(image_path).convert("RGB")

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
            self.preprocess(Image.open(path).convert("RGB")) for path in image_paths
        ]

        tensor = torch.stack(images).to(self.device)

        with torch.no_grad():
            features = self.model.encode_image(tensor)

        features = features / features.norm(
            dim=-1,
            keepdim=True,
        )

        return features.cpu().numpy().astype(np.float32)
