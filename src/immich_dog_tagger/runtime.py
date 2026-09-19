from functools import cache

from immich_dog_tagger.config import load_config
from immich_dog_tagger.dog_reid_embedder import DogReIDEmbedder
from immich_dog_tagger.yolo_detector import YOLODetector


@cache
def get_embedder() -> DogReIDEmbedder:
    return DogReIDEmbedder()


@cache
def get_yolo_detector() -> YOLODetector:
    return YOLODetector(load_config().yolo_model)
