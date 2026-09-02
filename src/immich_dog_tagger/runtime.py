from functools import cache

from immich_dog_tagger.config import load_config
from immich_dog_tagger.openclip_embedder import OpenClipEmbedder
from immich_dog_tagger.yolo_detector import YOLODetector


@cache
def get_embedder() -> OpenClipEmbedder:
    return OpenClipEmbedder()


@cache
def get_yolo_detector() -> YOLODetector:
    return YOLODetector(load_config().yolo_model)
