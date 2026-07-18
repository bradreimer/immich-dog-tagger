from pathlib import Path

import pytest

from immich_dog_tagger.database import create_database


@pytest.fixture
def engine(tmp_path: Path):
    return create_database(tmp_path)