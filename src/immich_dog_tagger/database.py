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
        # A write transaction (a pipeline job committing a batch, a review
        # action) briefly holds SQLite's single write lock. Without a
        # busy_timeout, any other connection that lands on that window fails
        # immediately with "database is locked" instead of waiting the
        # moment it takes for the lock to clear (issue #104).
        connect_args={"timeout": 30},
    )

    Base.metadata.create_all(engine)

    _ensure_identity_activation_column(engine)
    _ensure_classification_pass_columns(engine)
    _ensure_classification_pass_trend_columns(engine)
    _ensure_identity_species_column(engine)
    _ensure_crop_species_column(engine)
    _ensure_pipeline_job_visible_column(engine)
    _ensure_pipeline_job_cancel_requested_column(engine)
    _ensure_asset_metadata_columns(engine)

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


def _ensure_identity_species_column(engine) -> None:
    """
    DT-1110: identities gained a `species` column and their uniqueness
    changed from `name` alone to `(species, name)`, so a dog "Max" and a
    cat "Max" can coexist. SQLite cannot ALTER a table to add or change a
    UNIQUE constraint in place, so -- only for a database that predates this
    column -- rebuild the table: create the new shape, copy every existing
    row across with species='DOG' (the only species that existed before
    this ticket, so this is a behavior-preserving backfill, not a guess),
    then swap it in for the old table.

    Stored as 'DOG'/'CAT' (the enum member *name*), not 'dog'/'cat' (its
    value) -- SQLAlchemy's Enum(native_enum=False) looks columns up by
    member name, not value, when mapping a stored string back to the Python
    enum. A lowercase value here would round-trip through raw SQL fine but
    raise LookupError the moment the ORM tries to read it back.
    """
    inspector = inspect(engine)
    columns = {column["name"] for column in inspector.get_columns("identities")}

    if "species" in columns:
        return

    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE identities_new ("
            "id INTEGER NOT NULL PRIMARY KEY, "
            "species VARCHAR(8) NOT NULL DEFAULT 'DOG', "
            "name VARCHAR(64) NOT NULL, "
            "is_active BOOLEAN NOT NULL DEFAULT 1, "
            "UNIQUE (species, name)"
            ")"
        )
        connection.exec_driver_sql(
            "INSERT INTO identities_new (id, species, name, is_active) "
            "SELECT id, 'DOG', name, is_active FROM identities"
        )
        connection.exec_driver_sql("DROP TABLE identities")
        connection.exec_driver_sql("ALTER TABLE identities_new RENAME TO identities")


def _ensure_crop_species_column(engine) -> None:
    """
    DT-1110: crops gained a `species` column, set explicitly by
    DetectionService at creation time. A plain ADD COLUMN suffices here
    (unlike identities, no uniqueness constraint changes) -- and the
    DEFAULT 'DOG' is a correct backfill, not a guess: CropWriter only ever
    created a Crop for a "dog" detection before this ticket, so every
    existing crop already is one. Stored as the enum member name ('DOG'),
    not its value ('dog') -- see the identical note on
    _ensure_identity_species_column.
    """
    inspector = inspect(engine)
    columns = {column["name"] for column in inspector.get_columns("crops")}

    if "species" in columns:
        return

    with engine.begin() as connection:
        connection.exec_driver_sql(
            "ALTER TABLE crops ADD COLUMN species VARCHAR(8) NOT NULL DEFAULT 'DOG'"
        )


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


def _ensure_pipeline_job_visible_column(engine) -> None:
    """
    DT-1116: "Clear list" in the Job Queue UI used to only filter the
    frontend's local state, so a refresh brought every job straight back
    (github.com/bradreimer/immich-dog-tagger/issues/12). Every existing job
    defaults to visible=True on migration -- clearing is something an
    operator does going forward, not a retroactive change to what's
    currently displayed.
    """
    inspector = inspect(engine)
    columns = {column["name"] for column in inspector.get_columns("pipeline_jobs")}

    if "visible" in columns:
        return

    with engine.begin() as connection:
        connection.exec_driver_sql(
            "ALTER TABLE pipeline_jobs ADD COLUMN visible BOOLEAN NOT NULL DEFAULT 1"
        )


def _ensure_pipeline_job_cancel_requested_column(engine) -> None:
    """Issue #111: lets cancel_job() flag a RUNNING job for cancellation."""
    inspector = inspect(engine)
    columns = {column["name"] for column in inspector.get_columns("pipeline_jobs")}

    if "cancel_requested" in columns:
        return

    with engine.begin() as connection:
        connection.exec_driver_sql(
            "ALTER TABLE pipeline_jobs ADD COLUMN cancel_requested BOOLEAN NOT NULL DEFAULT 0"
        )


def _ensure_asset_metadata_columns(engine) -> None:
    """
    Issue #94: assets gained cached location/people/favorite fields sourced
    from Immich's own exifInfo/people/isFavorite. Plain ADD COLUMNs suffice
    -- no uniqueness/constraint changes -- and every default is a correct
    backfill for existing rows (nothing was known before this column
    existed), not a guess.
    """
    inspector = inspect(engine)
    columns = {column["name"] for column in inspector.get_columns("assets")}

    statements = []

    if "latitude" not in columns:
        statements.append("ALTER TABLE assets ADD COLUMN latitude FLOAT")

    if "longitude" not in columns:
        statements.append("ALTER TABLE assets ADD COLUMN longitude FLOAT")

    if "country" not in columns:
        statements.append("ALTER TABLE assets ADD COLUMN country VARCHAR(128)")

    if "state" not in columns:
        statements.append("ALTER TABLE assets ADD COLUMN state VARCHAR(128)")

    if "city" not in columns:
        statements.append("ALTER TABLE assets ADD COLUMN city VARCHAR(128)")

    if "is_favorite" not in columns:
        statements.append(
            "ALTER TABLE assets ADD COLUMN is_favorite BOOLEAN NOT NULL DEFAULT 0"
        )

    if "people" not in columns:
        statements.append(
            "ALTER TABLE assets ADD COLUMN people JSON NOT NULL DEFAULT '[]'"
        )

    if "metadata_synced_at" not in columns:
        statements.append("ALTER TABLE assets ADD COLUMN metadata_synced_at DATETIME")

    if not statements:
        return

    with engine.begin() as connection:
        for statement in statements:
            connection.exec_driver_sql(statement)
