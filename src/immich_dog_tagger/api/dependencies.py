from collections.abc import Generator
from functools import cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from immich_dog_tagger.config import load_config
from immich_dog_tagger.database import create_database
from immich_dog_tagger.embedder import Embedder
from immich_dog_tagger.runtime import get_embedder
from immich_dog_tagger.services.correction import ClassificationCorrectionService
from immich_dog_tagger.services.learner import Learner
from immich_dog_tagger.services.review_actions import ReviewActionService
from immich_dog_tagger.services.review_query import ReviewQueryService


@cache
def get_engine():
    config = load_config()

    return create_database(
        config.state_dir,
    )


def get_session() -> Generator[Session]:
    engine = get_engine()

    with Session(engine) as session:
        yield session


def get_review_query_service(
    session: Annotated[Session, Depends(get_session)],
) -> ReviewQueryService:
    return ReviewQueryService(session)


def get_review_action_service(
    session: Annotated[Session, Depends(get_session)],
) -> ReviewActionService:
    return ReviewActionService(session)


def get_correction_service(
    session: Annotated[Session, Depends(get_session)],
    embedder: Annotated[Embedder, Depends(get_embedder)],
) -> ClassificationCorrectionService:
    learner = Learner(
        embedder=embedder,
        session=session,
    )

    return ClassificationCorrectionService(
        session=session,
        learner=learner,
    )
