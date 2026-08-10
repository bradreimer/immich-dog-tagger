"""
Database initialization and access.
"""

from pathlib import Path

from sqlalchemy import create_engine, inspect

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

    _ensure_identity_activation_column(engine)

    return engine


def _ensure_identity_activation_column(engine) -> None:
    inspector = inspect(engine)
    columns = {column["name"] for column in inspector.get_columns("identities")}

    if "is_active" in columns:
        return

    with engine.begin() as connection:
        connection.exec_driver_sql(
            "ALTER TABLE identities ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT 1"
        )
