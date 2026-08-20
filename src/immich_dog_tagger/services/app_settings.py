"""
Owner-editable application settings, and the auto-reclassify trigger
(issue #149).

Two small things that share a premise: the owner should not have to
understand the classifier, or remember to press a button, to get the
benefit of the work they have already done.
"""

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from immich_dog_tagger.enums import PipelineOperation, TaggingSensitivity
from immich_dog_tagger.models import AppSetting
from immich_dog_tagger.policy import (
    DEFAULT_SENSITIVITY,
    ClassifierPolicy,
    policy_for,
)

logger = logging.getLogger(__name__)

SENSITIVITY_KEY = "tagging_sensitivity"


class AppSettingsService:
    def __init__(self, session: Session):
        self.session = session

    def sensitivity(self) -> TaggingSensitivity:
        """
        The owner's chosen tagging sensitivity, defaulting to balanced.

        Fails open to the default rather than raising if the stored value
        is unrecognised -- a value written by a newer version, or edited by
        hand, must not take classification down with it.
        """
        raw = self._get(SENSITIVITY_KEY)

        if raw is None:
            return DEFAULT_SENSITIVITY

        try:
            return TaggingSensitivity(raw)
        except ValueError:
            logger.warning(
                "Unrecognised tagging sensitivity %r; using %s",
                raw,
                DEFAULT_SENSITIVITY.value,
            )
            return DEFAULT_SENSITIVITY

    def set_sensitivity(self, sensitivity: TaggingSensitivity) -> TaggingSensitivity:
        """
        Change how cautious automatic tagging is.

        Applies to the next classification or Reclassify and never
        retroactively rewrites anything -- and, because it only moves the
        confident/needs-review boundary for *derived* predictions, it can
        never touch a reviewed label.
        """
        self._set(SENSITIVITY_KEY, sensitivity.value)

        logger.info("Tagging sensitivity set to %s", sensitivity.value)

        return sensitivity

    def policy(self) -> ClassifierPolicy:
        """
        The classifier policy implied by the owner's current setting.

        Every caller that needs a policy for a real run should come through
        here rather than reaching for `DEFAULT_POLICY`, or the owner's
        choice silently does nothing.
        """
        return policy_for(self.sensitivity())

    def _get(self, key: str) -> str | None:
        setting = self.session.get(AppSetting, key)

        return setting.value if setting is not None else None

    def _set(self, key: str, value: str) -> None:
        setting = self.session.get(AppSetting, key)

        if setting is None:
            self.session.add(AppSetting(key=key, value=value))
        else:
            setting.value = value

        self.session.commit()


class AutoReclassifyService:
    """
    Runs Reclassify on the owner's behalf once a batch of review work
    settles (issue #149).

    Reclassify is local, idempotent, and never mutates a reviewed label, so
    triggering it automatically is permitted by
    [ADR-006](../../../docs/adr/ADR-006-immich-operations-explicit-local-operations-on-demand.md) --
    unlike anything that touches Immich, which stays explicit. It runs
    *through the job system* rather than inline, so work the app started on
    its own is as visible in the job queue as work the owner started.
    """

    def __init__(self, session: Session, job_service):
        self.session = session
        self.job_service = job_service

    def request(self) -> bool:
        """
        Queue a Reclassify unless one is already pending or running.

        The debounce is the important part. Approving a cluster of 200
        photos is one settling batch, not 200, and the job runner permits
        one job at a time anyway -- so enqueueing per correction would
        build a backlog of identical passes, each undoing the last one's
        claim to be current.

        Returns whether a job was queued, so callers can report it.
        """
        if self._already_queued():
            return False

        self.job_service.create_job(
            operation=PipelineOperation.RECLASSIFY,
            progress_message="Queued automatically after review",
        )

        logger.info("Auto-reclassify queued after a settled review batch")

        return True

    def _already_queued(self) -> bool:
        from immich_dog_tagger.enums import PipelineJobStatus
        from immich_dog_tagger.models import PipelineJob

        return (
            self.session.scalar(
                select(PipelineJob.id)
                .where(
                    PipelineJob.operation == PipelineOperation.RECLASSIFY,
                    PipelineJob.status.in_(
                        (
                            PipelineJobStatus.PENDING,
                            PipelineJobStatus.RUNNING,
                        )
                    ),
                )
                .limit(1)
            )
            is not None
        )
