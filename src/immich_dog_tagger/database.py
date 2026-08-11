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
    _ensure_classification_pass_columns(engine)
    _ensure_classification_pass_trend_columns(engine)

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


def _ensure_classification_pass_columns(engine) -> None:
    inspector = inspect(engine)
    columns = {
        column["name"] for column in inspector.get_columns("crop_classifications")
    }

    statements = []

    if "classifier_version" not in columns:
        statements.append(
            "ALTER TABLE crop_classifications ADD COLUMN classifier_version VARCHAR(32)"
        )

    if "classification_pass_id" not in columns:
        statements.append(
            "ALTER TABLE crop_classifications ADD COLUMN classification_pass_id INTEGER "
            "REFERENCES classification_passes(id)"
        )

    if "embedding" not in columns:
        statements.append("ALTER TABLE crop_classifications ADD COLUMN embedding BLOB")

    if not statements:
        return

    with engine.begin() as connection:
        for statement in statements:
            connection.exec_driver_sql(statement)


def _ensure_classification_pass_trend_columns(engine) -> None:
    inspector = inspect(engine)
    columns = {
        column["name"] for column in inspector.get_columns("classification_passes")
    }

    statements = []

    if "labeled_example_count" not in columns:
        statements.append(
            "ALTER TABLE classification_passes ADD COLUMN labeled_example_count INTEGER"
        )

    if "review_queue_size" not in columns:
        statements.append(
            "ALTER TABLE classification_passes ADD COLUMN review_queue_size INTEGER"
        )

    if not statements:
        return

    with engine.begin() as connection:
        for statement in statements:
            connection.exec_driver_sql(statement)
