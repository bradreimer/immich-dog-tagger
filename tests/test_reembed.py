from pathlib import Path

import numpy as np
from sqlalchemy.orm import Session

from immich_dog_tagger.embedder import LEGACY_OPENCLIP_MODEL_ID
from immich_dog_tagger.embeddings import embedding_to_blob
from immich_dog_tagger.enums import ClassificationSources, EmbeddingSources, Species
from immich_dog_tagger.models import (
    Asset,
    Crop,
    CropClassification,
    Detection,
    EmbeddingExample,
    Identity,
)
from immich_dog_tagger.services.reembed import ReembedService


class FakeEmbedder:
    MODEL_ID = "fake:v2"

    def embed_batch(self, paths):
        return np.array([[9, 9, 9] for _ in paths], dtype=np.float32)


def _seed(session, tmp_path):
    identity = Identity(name="Fibs", species=Species.DOG)
    session.add(identity)
    session.flush()

    example_path = tmp_path / "fibs-ref.jpg"
    example_path.write_bytes(b"fake")

    example = EmbeddingExample(
        identity_id=identity.id,
        crop_path=str(example_path),
        embedding=embedding_to_blob(np.array([1, 0, 0], dtype=np.float32)),
        source=EmbeddingSources.BOOTSTRAP,
    )
    session.add(example)

    missing_example = EmbeddingExample(
        identity_id=identity.id,
        crop_path=str(tmp_path / "missing.jpg"),
        embedding=embedding_to_blob(np.array([1, 0, 0], dtype=np.float32)),
        source=EmbeddingSources.BOOTSTRAP,
    )
    session.add(missing_example)

    asset = Asset(immich_asset_id="a1", extension="jpg")
    session.add(asset)
    session.flush()

    detection = Detection(
        asset_id=asset.id,
        label="dog",
        confidence=0.9,
        x1=0,
        y1=0,
        x2=10,
        y2=10,
    )
    session.add(detection)
    session.flush()

    auto_crop_path = tmp_path / "auto-crop.jpg"
    auto_crop_path.write_bytes(b"fake")
    auto_crop = Crop(
        detection_id=detection.id,
        path=str(auto_crop_path),
        species=Species.DOG,
    )
    session.add(auto_crop)
    session.flush()

    auto_classification = CropClassification(
        crop=auto_crop,
        identity="Fibs",
        confidence=0.9,
        candidates=[],
        source=ClassificationSources.AUTO,
        embedding=embedding_to_blob(np.array([1, 0, 0], dtype=np.float32)),
    )
    session.add(auto_classification)

    review_crop_path = tmp_path / "review-crop.jpg"
    review_crop_path.write_bytes(b"fake")
    review_crop = Crop(
        detection_id=detection.id,
        path=str(review_crop_path),
        species=Species.DOG,
    )
    session.add(review_crop)
    session.flush()

    review_classification = CropClassification(
        crop=review_crop,
        identity="Fibs",
        confidence=1.0,
        candidates=[],
        source=ClassificationSources.REVIEW,
        embedding=embedding_to_blob(np.array([0, 1, 0], dtype=np.float32)),
    )
    session.add(review_classification)

    pending_crop_path = tmp_path / "pending-crop.jpg"
    pending_crop_path.write_bytes(b"fake")
    pending_crop = Crop(
        detection_id=detection.id,
        path=str(pending_crop_path),
        species=Species.DOG,
    )
    session.add(pending_crop)
    session.flush()

    session.commit()

    return {
        "example": example,
        "missing_example": missing_example,
        "auto_classification": auto_classification,
        "review_classification": review_classification,
        "pending_crop": pending_crop,
    }


def test_reembed_examples_recomputes_and_skips_missing_files(engine, tmp_path: Path):
    with Session(engine) as session:
        seeded = _seed(session, tmp_path)

        done, skipped = ReembedService(session, FakeEmbedder()).reembed_examples()

        assert done == 1
        assert skipped == 1

        session.refresh(seeded["example"])
        session.refresh(seeded["missing_example"])

        assert seeded["example"].embedding_model == "fake:v2"
        assert seeded["example"].embedding == embedding_to_blob(
            np.array([9, 9, 9], dtype=np.float32)
        )

        # Missing crop file: left exactly as it was, not silently corrupted.
        assert seeded["missing_example"].embedding_model == LEGACY_OPENCLIP_MODEL_ID
        assert seeded["missing_example"].embedding == embedding_to_blob(
            np.array([1, 0, 0], dtype=np.float32)
        )


def test_reembed_classifications_recomputes_vector_without_touching_labels(
    engine, tmp_path: Path
):
    with Session(engine) as session:
        seeded = _seed(session, tmp_path)

        done, skipped = ReembedService(
            session, FakeEmbedder()
        ).reembed_classifications()

        # Only the two classifications that already had an embedding -- the pending crop
        # (no classification at all) is untouched, it'll be embedded by a normal classify run.
        assert done == 2
        assert skipped == 0

        session.refresh(seeded["auto_classification"])
        session.refresh(seeded["review_classification"])

        for classification in (
            seeded["auto_classification"],
            seeded["review_classification"],
        ):
            assert classification.embedding_model == "fake:v2"
            assert classification.embedding == embedding_to_blob(
                np.array([9, 9, 9], dtype=np.float32)
            )

        # The whole point: a reviewed row's identity/confidence/source are never touched, only
        # its embedding vector.
        assert seeded["review_classification"].identity == "Fibs"
        assert seeded["review_classification"].confidence == 1.0
        assert seeded["review_classification"].source == ClassificationSources.REVIEW


def test_reembed_all_combines_both(engine, tmp_path: Path):
    with Session(engine) as session:
        _seed(session, tmp_path)

        summary = ReembedService(session, FakeEmbedder()).reembed_all()

        assert summary.examples_reembedded == 1
        assert summary.examples_skipped == 1
        assert summary.classifications_reembedded == 2
        assert summary.classifications_skipped == 0
