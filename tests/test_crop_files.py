"""Tests for discarding a crop file without breaking a learned example (issue #380)."""

from pathlib import Path

from sqlalchemy.orm import Session

from immich_dog_tagger.models import EmbeddingExample, Identity
from immich_dog_tagger.services.crop_files import discard_crop_file


def _make_example(session: Session, path: Path) -> EmbeddingExample:
    identity = Identity(name="Fido")
    session.add(identity)
    session.flush()
    example = EmbeddingExample(
        identity_id=identity.id,
        crop_path=str(path),
        embedding=b"\x00" * 4,
        source="review",
    )
    session.add(example)
    session.flush()
    return example


def test_deletes_a_crop_file_no_example_uses(session, tmp_path):
    crop = tmp_path / "asset_0.jpg"
    crop.write_bytes(b"crop")

    discard_crop_file(session, str(crop))

    assert not crop.exists()


def test_moves_a_crop_file_an_example_uses_and_updates_the_example(session, tmp_path):
    crop = tmp_path / "asset_0.jpg"
    crop.write_bytes(b"learned crop")
    example = _make_example(session, crop)

    discard_crop_file(session, str(crop))

    kept = Path(example.crop_path)
    assert not crop.exists()
    assert kept != crop
    assert kept.parent == crop.parent
    assert kept.name.startswith("asset_0_example_")
    assert kept.read_bytes() == b"learned crop"


def test_leaves_an_example_alone_when_its_file_is_already_missing(session, tmp_path):
    crop = tmp_path / "asset_0.jpg"
    example = _make_example(session, crop)

    discard_crop_file(session, str(crop))

    assert example.crop_path == str(crop)
