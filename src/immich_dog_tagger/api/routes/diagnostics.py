from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from immich_dog_tagger.api.dependencies import (
    get_asset_repair_service,
    get_config,
    get_engine,
    get_job_service,
    get_session,
    get_stale_detection_service,
)
from immich_dog_tagger.api.schemas import StaleDetectionRepairResponse
from immich_dog_tagger.config import Config
from immich_dog_tagger.services.asset_repair import AssetRepairService
from immich_dog_tagger.services.backup import BackupService
from immich_dog_tagger.services.derived_data import check_derived_data
from immich_dog_tagger.services.job_recovery import (
    STUCK_JOB_IDLE_THRESHOLD,
    find_stuck_jobs,
)
from immich_dog_tagger.services.jobs import PipelineJobService
from immich_dog_tagger.services.scheduler_loop import SchedulerHealth
from immich_dog_tagger.services.stale_detection import StaleDetectionService

router = APIRouter()


@router.get("/diagnostics")
def diagnostics(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    engine: Annotated[Engine, Depends(get_engine)],
    config: Annotated[Config, Depends(get_config)],
    job_service: Annotated[PipelineJobService, Depends(get_job_service)],
):
    scheduler_health: SchedulerHealth | None = getattr(
        request.app.state, "scheduler_health", None
    )

    # Job summary
    job_counts: dict[str, int] = {
        status.value: count for status, count in job_service.status_counts().items()
    }

    recent_failures = job_service.recent_failures(limit=5)

    # Not "every RUNNING/PENDING job" -- an active job is a healthy job
    # until it stops making progress (issue #134).
    stuck_jobs = find_stuck_jobs(session)

    # Backup status
    backup_svc = BackupService(config.state_dir)
    backups = backup_svc.list_backups()
    last_backup = backups[-1] if backups else None

    # Derived data. Uses its own short-lived session (issue #317) -- the per-file disk
    # scan this does must not hold `session` above checked out of the pool for its
    # duration.
    derived_report = check_derived_data(engine, config.cache_dir)

    # Stale (EXIF-orientation) detections
    stale_report = StaleDetectionService(session).check()

    return {
        "db": {
            "healthy": True,
        },
        "scheduler": scheduler_health.as_dict() if scheduler_health else None,
        "jobs": {
            "counts": job_counts,
            "stuck_threshold_seconds": int(STUCK_JOB_IDLE_THRESHOLD.total_seconds()),
            "stuck": [
                {
                    "id": entry.job.id,
                    "operation": entry.job.operation.value,
                    "status": entry.job.status.value,
                    "created_at": entry.job.created_at.isoformat()
                    if entry.job.created_at
                    else None,
                    "last_activity_at": entry.job.last_activity_at.isoformat()
                    if entry.job.last_activity_at
                    else None,
                    "idle_seconds": entry.idle_seconds,
                }
                for entry in stuck_jobs
            ],
            "recent_failures": [
                {
                    "id": j.id,
                    "operation": j.operation.value,
                    "error_message": j.error_message,
                    "completed_at": j.completed_at.isoformat()
                    if j.completed_at
                    else None,
                }
                for j in recent_failures
            ],
        },
        "backup": {
            "last_backup_at": last_backup.created_at.isoformat()
            if last_backup
            else None,
            "backup_count": len(backups),
            "has_backup": last_backup is not None,
        },
        "derived_data": derived_report.as_dict(),
        "stale_detections": stale_report.as_dict(),
    }


@router.post(
    "/diagnostics/stale-detections/repair",
    response_model=StaleDetectionRepairResponse,
)
def repair_stale_detections(
    service: Annotated[StaleDetectionService, Depends(get_stale_detection_service)],
    asset_repair_service: Annotated[
        AssetRepairService, Depends(get_asset_repair_service)
    ],
    include_reviewed: bool = False,
):
    # Batch-runs the existing per-photo Repair action (issue #226) over every
    # currently-flagged asset. Reviewed assets are skipped unless the caller
    # explicitly opts in (include_reviewed=True) -- repairing one discards
    # its review history, so that has to be a deliberate choice made with
    # the count from GET /diagnostics.stale_detections.reviewed_at_risk in
    # hand, never the silent default.
    summary = service.repair(asset_repair_service, include_reviewed=include_reviewed)

    return StaleDetectionRepairResponse.from_summary(summary)
