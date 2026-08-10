from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from immich_dog_tagger.api.dependencies import get_config, get_session
from immich_dog_tagger.config import Config
from immich_dog_tagger.enums import PipelineJobStatus
from immich_dog_tagger.models import PipelineJob
from immich_dog_tagger.services.backup import BackupService
from immich_dog_tagger.services.derived_data import DerivedDataService
from immich_dog_tagger.services.scheduler_loop import SchedulerHealth

router = APIRouter()


@router.get("/diagnostics")
def diagnostics(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    config: Annotated[Config, Depends(get_config)],
):
    scheduler_health: SchedulerHealth | None = getattr(
        request.app.state, "scheduler_health", None
    )

    # Job summary
    job_rows = session.execute(
        select(PipelineJob.status, func.count(PipelineJob.id)).group_by(
            PipelineJob.status
        )
    ).all()
    job_counts: dict[str, int] = {str(row[0].value): row[1] for row in job_rows}

    recent_failures = session.scalars(
        select(PipelineJob)
        .where(PipelineJob.status == PipelineJobStatus.FAILED)
        .order_by(PipelineJob.completed_at.desc())
        .limit(5)
    ).all()

    stuck_jobs = session.scalars(
        select(PipelineJob).where(
            PipelineJob.status.in_(
                [PipelineJobStatus.RUNNING, PipelineJobStatus.PENDING]
            )
        )
    ).all()

    # Backup status
    backup_svc = BackupService(config.state_dir)
    backups = backup_svc.list_backups()
    last_backup = backups[-1] if backups else None

    # Derived data
    derived_svc = DerivedDataService(session, config.cache_dir)
    derived_report = derived_svc.check()

    return {
        "db": {
            "healthy": True,
        },
        "scheduler": scheduler_health.as_dict() if scheduler_health else None,
        "jobs": {
            "counts": job_counts,
            "stuck": [
                {
                    "id": j.id,
                    "operation": j.operation.value,
                    "status": j.status.value,
                    "created_at": j.created_at.isoformat() if j.created_at else None,
                }
                for j in stuck_jobs
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
    }
