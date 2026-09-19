"""
Dog re-identification image embedding implementation.

Replaces the previous OpenCLIP-based embedder (ADR-010): CLIP is trained to align an image with a
caption, not to separate individuals of the same species/breed, so its embedding space puts a
ceiling on how well nearest-neighbor matching (IdentityClassifier) can tell two dogs apart.
MegaDescriptor is trained with metric learning specifically for individual animal
re-identification -- the property classification actually depends on.
"""

from pathlib import Path

import numpy as np
import timm
import torch
from timm.data import create_transform, resolve_model_data_config

from .images import open_upright

#: hf-hub:BVRA/MegaDescriptor-L-384 -- see ADR-010 for why this model and this variant.
DEFAULT_MODEL_NAME = "hf-hub:BVRA/MegaDescriptor-L-384"


class DogReIDEmbedder:
    #: Stamped onto EmbeddingExample.embedding_model / CropClassification.embedding_model
    #: (see database.py's additive migration) so a stored vector is always traceable to the
    #: model that produced it -- comparing vectors from two different models is meaningless.
    MODEL_ID = f"timm:{DEFAULT_MODEL_NAME}"

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL_NAME,
    ):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        # num_classes=0 drops the training-time classification head, leaving the pooled
        # re-identification embedding as the model's output.
        self.model = timm.create_model(
            model_name,
            pretrained=True,
            num_classes=0,
        )

        self.model.to(self.device)

        self.model.eval()

        data_config = resolve_model_data_config(self.model)

        self.preprocess = create_transform(
            **data_config,
            is_training=False,
        )

    def embed(
        self,
        image_path: Path,
    ) -> np.ndarray:

        image = open_upright(image_path).convert("RGB")

        tensor = self.preprocess(image).unsqueeze(0).to(self.device)

        with torch.no_grad():
            features = self.model(tensor)

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
            features = self.model(tensor)

        features = features / features.norm(
            dim=-1,
            keepdim=True,
        )

        return features.cpu().numpy().astype(np.float32)
