"""
Database initialization and access.
"""

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from .models import Base


def create_database(state_dir: Path):
    """
    Create or open the application database.
    """

    state_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    database_path = state_dir / "state.db"

    engine = create_engine(
        f"sqlite:///{database_path}",
    )

    Base.metadata.create_all(engine)

    return engine


def create_session(engine) -> Session:
    """
    Create a database session.
    """

    return Session(engine)
