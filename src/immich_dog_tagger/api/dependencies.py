from collections.abc import Generator
from fastapi import Depends
from sqlalchemy.orm import Session

from immich_dog_tagger.config import load_config
from immich_dog_tagger.database import create_database
from immich_dog_tagger.runtime import get_embedder
from immich_dog_tagger.services.correction import ClassificationCorrectionService
from immich_dog_tagger.services.learner import Learner
from immich_dog_tagger.services.review_query import ReviewQueryService


def get_session() -> Generator[Session, None, None]:
    config = load_config()

    engine = create_database(
        config.state_dir,
    )

    with Session(engine) as session:
        yield session


def get_review_query_service(
    session: Session,
) -> ReviewQueryService:
    return ReviewQueryService(session)


def get_correction_service(
    session: Session = Depends(get_session),
    embedder=Depends(get_embedder),
) -> ClassificationCorrectionService:
    learner = Learner(
        embedder=embedder,
        session=session,
    )

    return ClassificationCorrectionService(
        session=session,
        learner=learner,
    )
