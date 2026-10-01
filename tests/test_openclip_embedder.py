from immich_dog_tagger.embedder import LEGACY_OPENCLIP_MODEL_ID


def test_openclip_embedder_imports():
    from immich_dog_tagger.openclip_embedder import OpenClipEmbedder

    assert OpenClipEmbedder is not None


def test_openclip_embedder_keeps_legacy_model_id():
    # Rows stamped before ADR-010 must stay comparable with new OpenCLIP vectors (ADR-011).
    from immich_dog_tagger.openclip_embedder import OpenClipEmbedder

    assert OpenClipEmbedder.MODEL_ID == LEGACY_OPENCLIP_MODEL_ID


def test_openclip_embedder_conforms_to_embedder_protocol():
    from immich_dog_tagger.openclip_embedder import OpenClipEmbedder

    assert hasattr(OpenClipEmbedder, "embed")
    assert hasattr(OpenClipEmbedder, "embed_batch")
