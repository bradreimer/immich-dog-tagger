def test_dog_reid_embedder_imports():
    from immich_dog_tagger.dog_reid_embedder import DogReIDEmbedder

    assert DogReIDEmbedder is not None
    assert DogReIDEmbedder.MODEL_ID


def test_dog_reid_embedder_conforms_to_embedder_protocol():
    from immich_dog_tagger.dog_reid_embedder import DogReIDEmbedder

    assert hasattr(DogReIDEmbedder, "embed")
    assert hasattr(DogReIDEmbedder, "embed_batch")
