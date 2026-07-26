from immich_dog_tagger.api.app import create_app
from immich_dog_tagger.api.dependencies import get_embedder, get_session
from immich_dog_tagger.database import create_database
from pathlib import Path

import pytest

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


class FakeEmbedder:
    def embed(self, path):
        import numpy as np

        return np.array(
            [1, 0, 0],
            dtype=np.float32,
        )


@pytest.fixture
def api_client(engine):
    app = create_app()

    def override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_embedder] = lambda: FakeEmbedder()

    return TestClient(app)


@pytest.fixture
def engine(tmp_path: Path):
    return create_database(tmp_path)
