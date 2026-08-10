"""
Production recovery drill — exercises the full backup/restore/job-recovery/
derived-data path end-to-end. Satisfies DT-0926.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from sqlalchemy.orm import Session

from immich_dog_tagger.enums import PipelineJobStatus, PipelineOperation
from immich_dog_tagger.models import (
    EmbeddingExample,
    Identity,
)
from immich_dog_tagger.services.backup import BackupService
from immich_dog_tagger.services.derived_data import DerivedDataService
from immich_dog_tagger.services.job_recovery import recover_interrupted_jobs
from immich_dog_tagger.services.jobs import PipelineJobService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _seed_authoritative_state(session: Session, tmp_path: Path) -> dict:
    """Create minimal authoritative state that must survive backup/restore."""
    identity = Identity(name="TestDog")
    session.add(identity)
    session.flush()

    example_file = tmp_path / "example.jpg"
    example_file.write_bytes(b"fake-image")

    example = EmbeddingExample(
        identity_id=identity.id,
        crop_path=str(example_file),
        embedding=b"\x01\x02\x03\x04",
        source="bootstrap",
    )
    session.add(example)
    session.flush()

    job_svc = PipelineJobService(session)
    job = job_svc.create_job(operation=PipelineOperation.FULL_PIPELINE)
    job.transition_to(PipelineJobStatus.RUNNING)
    job.transition_to(PipelineJobStatus.COMPLETED)
    session.commit()

    return {
        "identity_id": identity.id,
        "example_id": example.id,
        "example_path": str(example_file),
        "job_id": job.id,
    }


# ---------------------------------------------------------------------------
# Drill
# ---------------------------------------------------------------------------


def test_recovery_drill_backup_restore_and_state_verification(engine, tmp_path):
    """
    1. Seed authoritative state (identities, examples, jobs).
    2. Create backup.
    3. Verify backup integrity.
    4. Simulate database loss.
    5. Restore backup.
    6. Verify authoritative state is intact.
    """

    state_dir = tmp_path / "state"
    state_dir.mkdir()

    # Write the engine's DB to a state_dir so BackupService can find it
    db_path = engine.url.database
    import shutil

    shutil.copy(db_path, state_dir / "state.db")

    with Session(engine) as session:
        ids = _seed_authoritative_state(session, tmp_path)

    # Copy seeded DB into state_dir
    shutil.copy(db_path, state_dir / "state.db")

    # Step 2: backup
    svc = BackupService(state_dir)
    result = svc.create_backup()
    assert result.path.exists()

    # Step 3: validate
    svc.validate_backup(result.path)

    # Step 4: simulate loss — corrupt the live db
    (state_dir / "state.db").write_bytes(b"simulated corruption or deletion")

    # Step 5: restore
    rollback = svc.restore_backup(result.path)
    assert rollback.exists()

    # Step 6: verify authoritative state in restored db
    restored_conn = sqlite3.connect(str(state_dir / "state.db"))
    row = restored_conn.execute(
        "SELECT name FROM identities WHERE id=?", (ids["identity_id"],)
    ).fetchone()
    restored_conn.close()
    assert row is not None
    assert row[0] == "TestDog"


def test_recovery_drill_interrupted_job_recovery(engine):
    """
    1. Create a job and leave it RUNNING (simulating crash).
    2. Run recovery.
    3. Verify job is FAILED with a recoverable error message.
    """
    from immich_dog_tagger.models import PipelineJob

    with Session(engine) as session:
        svc = PipelineJobService(session)
        job = svc.create_job(operation=PipelineOperation.FULL_PIPELINE)
        job_id = job.id
        job.transition_to(PipelineJobStatus.RUNNING)
        session.commit()

        result = recover_interrupted_jobs(session)

    assert result.failed == 1

    with Session(engine) as session:
        recovered = session.get(PipelineJob, job_id)
        assert recovered.status is PipelineJobStatus.FAILED
        assert recovered.error_message is not None
        assert "Interrupted" in recovered.error_message


def test_recovery_drill_derived_data_detection_and_guidance(session, tmp_path):
    """
    1. Seed a crop reference whose file is missing.
    2. Run derived-data check.
    3. Verify guidance directs user to the correct rebuild command.
    """
    from immich_dog_tagger.models import Asset, AssetStatus, Crop, Detection

    asset = Asset(
        immich_asset_id="drill-asset",
        checksum="abc",
        extension=".jpg",
        status=AssetStatus.DOWNLOADED,
    )
    session.add(asset)
    session.flush()

    det = Detection(
        asset_id=asset.id, label="dog", confidence=0.9, x1=0, y1=0, x2=10, y2=10
    )
    session.add(det)
    session.flush()

    crop = Crop(detection_id=det.id, path=str(tmp_path / "missing_crop.jpg"))
    session.add(crop)
    session.commit()

    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()

    svc = DerivedDataService(session, cache_dir)
    report = svc.check()

    assert len(report.missing_crops) >= 1
    guidance = DerivedDataService.rebuild_guidance(report)
    assert any("detect" in line for line in guidance)
