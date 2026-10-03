from functools import cache

from immich_dog_tagger.config import load_config
from immich_dog_tagger.grounding_dino_detector import GroundingDinoDetector
from immich_dog_tagger.openclip_embedder import OpenClipEmbedder
from immich_dog_tagger.yolo_detector import YOLODetector


@cache
def get_embedder() -> OpenClipEmbedder:
    return OpenClipEmbedder()


@cache
def get_yolo_detector() -> YOLODetector:
    return YOLODetector(load_config().yolo_model)


@cache
def get_look_harder_detector() -> GroundingDinoDetector:
    # Cached for the process's lifetime, like the other models: the weights
    # load on its first detect(), not here (issue #390).
    return GroundingDinoDetector(load_config().look_harder_model)
