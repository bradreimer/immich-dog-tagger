import pytest
from sqlalchemy.orm import Session

from immich_dog_tagger.services.job_execution import _learn_handler


class DummyProgress:
    def set(self, current=None, total=None, message=None):
        return None


def test_learn_handler_requires_reference_root_when_identity_and_directory_not_set(
    engine, tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)

    with Session(engine) as session:
        handler = _learn_handler(session, {})
        with pytest.raises(ValueError, match="reference directory not found"):
            handler(DummyProgress())


def test_learn_handler_does_not_fallback_to_training_directory(
    engine, tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "training").mkdir()

    with Session(engine) as session:
        handler = _learn_handler(session, {})
        with pytest.raises(ValueError, match="reference directory not found"):
            handler(DummyProgress())


def test_learn_handler_uses_reference_root_when_present(engine, tmp_path, monkeypatch):
    import numpy as np

    class FakeEmbedder:
        def embed(self, image_path):
            return np.array([0.1, 0.2, 0.3], dtype=np.float32)

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "immich_dog_tagger.services.job_execution.get_embedder",
        lambda: FakeEmbedder(),
    )
    refs = tmp_path / "references" / "Fibs"
    refs.mkdir(parents=True)
    (refs / "sample.jpg").write_bytes(b"fake")

    with Session(engine) as session:
        handler = _learn_handler(session, {})
        result = handler(DummyProgress())

    assert result["identities"] == 1
    assert result["imported"] == 1
