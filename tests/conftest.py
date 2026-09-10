from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.orm import Session

from immich_dog_tagger.api.app import create_app
from immich_dog_tagger.api.dependencies import (
    get_embedder,
    get_engine,
    get_job_dispatcher,
    get_session,
)
from immich_dog_tagger.database import create_database
from immich_dog_tagger.models import Crop, CropClassification


class QueryCounter:
    """
    Counts SQL statements issued against an engine inside a `with` block --
    the shape of check DT-1008 introduced for N+1 regressions, shared here
    so endpoint-level tests can pin query counts too.
    """

    def __init__(self, engine):
        self.count = 0
        self.engine = engine

    def __enter__(self):
        event.listen(self.engine, "before_cursor_execute", self._on_execute)
        return self

    def __exit__(self, *exc_info):
        event.remove(self.engine, "before_cursor_execute", self._on_execute)

    def _on_execute(self, conn, cursor, statement, parameters, context, executemany):
        self.count += 1


class FakeEmbedder:
    def embed(self, path):
        import numpy as np

        return np.array(
            [1, 0, 0],
            dtype=np.float32,
        )


class FakeJobDispatcher:
    def __init__(self):
        self.triggers = 0

    def trigger(self):
        self.triggers += 1


@pytest.fixture(autouse=True)
def test_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("YOLO_MODEL", str(tmp_path / "yolo11n.pt"))


@pytest.fixture
def api_client(engine):
    app = create_app()
    dispatcher = FakeJobDispatcher()

    def override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    # get_engine() is process-cached (functools.cache), so routes that take
    # the engine directly (crops.py's crop route, embedding_examples.py --
    # both open their own short-lived session rather than a
    # request-scoped one, issue #277) must be pointed at this test's
    # isolated engine too, not whatever get_engine() resolved to first in
    # this test process.
    app.dependency_overrides[get_engine] = lambda: engine
    app.dependency_overrides[get_embedder] = lambda: FakeEmbedder()
    app.dependency_overrides[get_job_dispatcher] = lambda: dispatcher

    app.state.fake_job_dispatcher = dispatcher

    return TestClient(app)


@pytest.fixture
def engine(tmp_path: Path):
    return create_database(tmp_path)


@pytest.fixture
def session(engine):
    with Session(engine) as session:
        yield session


def create_test_classification(session: Session) -> CropClassification:
    crop = Crop(
        detection_id=1,
        path="test.jpg",
    )

    session.add(crop)
    session.flush()

    classification = CropClassification(
        crop=crop,
        identity=None,
        confidence=0.50,
    )

    session.add(classification)
    session.commit()

    return classification
