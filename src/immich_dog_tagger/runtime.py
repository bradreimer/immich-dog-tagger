from functools import cache
from immich_dog_tagger.openclip_embedder import OpenClipEmbedder


@cache
def get_embedder() -> OpenClipEmbedder:
    return OpenClipEmbedder()
