"""
Owner-facing tagging sensitivity, and auto-reclassify (issue #149).
"""

import re
from pathlib import Path

from sqlalchemy.orm import Session

from immich_dog_tagger.enums import (
    PipelineJobStatus,
    PipelineOperation,
    TaggingSensitivity,
)
from immich_dog_tagger.models import AppSetting, PipelineJob
from immich_dog_tagger.policy import (
    DEFAULT_POLICY,
    DEFAULT_SENSITIVITY,
    SENSITIVITY_THRESHOLDS,
    ClassificationDecision,
    policy_for,
)
from immich_dog_tagger.services.app_settings import (
    AppSettingsService,
    AutoReclassifyService,
)
from immich_dog_tagger.services.jobs import PipelineJobService
from tests.conftest import FakeJobDispatcher


def test_sensitivity_defaults_to_balanced(engine):
    with Session(engine) as session:
        assert AppSettingsService(session).sensitivity() is TaggingSensitivity.BALANCED


def test_sensitivity_round_trips(engine):
    with Session(engine) as session:
        service = AppSettingsService(session)

        service.set_sensitivity(TaggingSensitivity.CAUTIOUS)

        assert service.sensitivity() is TaggingSensitivity.CAUTIOUS

    # Persisted, not just held in memory.
    with Session(engine) as session:
        assert AppSettingsService(session).sensitivity() is TaggingSensitivity.CAUTIOUS


def test_an_unrecognised_stored_value_fails_open_to_the_default(engine):
    """
    A value written by a newer version, or edited by hand, must not take
    classification down with it.
    """
    with Session(engine) as session:
        session.add(AppSetting(key="tagging_sensitivity", value="reckless"))
        session.commit()

        assert AppSettingsService(session).sensitivity() is DEFAULT_SENSITIVITY


def test_the_balanced_policy_is_unchanged_from_before_the_setting_existed(engine):
    """
    The default has to keep meaning exactly what it always meant, or every
    existing stored prediction's version string silently changes meaning.
    """
    policy = policy_for(TaggingSensitivity.BALANCED)

    assert policy.version == DEFAULT_POLICY.version == "v1"
    assert policy.confident_threshold == DEFAULT_POLICY.confident_threshold


def test_a_non_default_sensitivity_is_traceable_from_the_version(engine):
    """
    classifier_version exists so a stored prediction can be traced back to
    the configuration that produced it -- a configurable threshold has to
    keep that guarantee.
    """
    assert policy_for(TaggingSensitivity.CAUTIOUS).version == "v1-cautious"
    assert policy_for(TaggingSensitivity.EAGER).version == "v1-eager"


def test_sensitivity_moves_the_confident_boundary_in_the_right_direction(engine):
    cautious = policy_for(TaggingSensitivity.CAUTIOUS)
    balanced = policy_for(TaggingSensitivity.BALANCED)
    eager = policy_for(TaggingSensitivity.EAGER)

    assert cautious.confident_threshold > balanced.confident_threshold
    assert eager.confident_threshold < balanced.confident_threshold

    # A match that balanced would send to review is tagged automatically
    # under eager, and one balanced would tag is sent to review under
    # cautious. That is the whole owner-visible effect.
    borderline = 0.77

    assert (
        eager.decide(identity="Fibs", similarity=borderline)
        is ClassificationDecision.CONFIDENT
    )
    assert (
        balanced.decide(identity="Fibs", similarity=borderline)
        is ClassificationDecision.NEEDS_REVIEW
    )
    assert (
        cautious.decide(identity="Fibs", similarity=0.83)
        is ClassificationDecision.NEEDS_REVIEW
    )


def test_every_sensitivity_has_a_threshold(engine):
    assert set(SENSITIVITY_THRESHOLDS) == set(TaggingSensitivity)


def test_no_classification_threshold_literal_lives_outside_policy(engine):
    """
    The v1.0.0 rule: one module owns the confident/needs-review boundary.
    Making the threshold configurable is exactly the change that tempts a
    second copy of the number into existence.

    Two pre-existing uses of 0.80 are allowed through, because they are
    different quantities that happen to share a value, and collapsing them
    into the classifier policy would couple things that should move
    independently:

    - `sync_policy.py` -- how confident a prediction must be before it is
      published to an Immich album. An owner could reasonably want eager
      tagging and cautious publishing.
    - `review_query.py` -- the edges of a display histogram, which describe
      the data rather than deciding anything.
    """
    source_root = Path(__file__).resolve().parent.parent / "src" / "immich_dog_tagger"

    allowed = {
        Path("services/sync_policy.py"),
        Path("services/review_query.py"),
    }

    literals = re.compile(r"0\.(?:74|80|86)\b")
    offenders = []

    for path in source_root.rglob("*.py"):
        relative = path.relative_to(source_root)

        if path.name == "policy.py" or relative in allowed:
            continue

        for number, line in enumerate(path.read_text().splitlines(), start=1):
            code = line.split("#", 1)[0]

            if literals.search(code):
                offenders.append(f"{relative}:{number}")

    assert offenders == [], (
        "classification-threshold literals found outside policy.py: "
        + ", ".join(offenders)
    )


def test_the_sensitivity_thresholds_exist_only_in_policy(engine):
    """
    The two values this issue introduces have no legitimate second home --
    unlike 0.80, they mean nothing except "cautious" and "eager".
    """
    source_root = Path(__file__).resolve().parent.parent / "src" / "immich_dog_tagger"

    literals = re.compile(r"0\.(?:74|86)\b")

    for path in source_root.rglob("*.py"):
        if path.name == "policy.py":
            continue

        for line in path.read_text().splitlines():
            assert not literals.search(line.split("#", 1)[0]), (
                f"sensitivity threshold literal outside policy.py in {path}"
            )


def test_auto_reclassify_queues_a_job(engine):
    with Session(engine) as session:
        dispatcher = FakeJobDispatcher()
        service = AutoReclassifyService(
            session, PipelineJobService(session), dispatcher
        )

        assert service.request() is True

        jobs = session.query(PipelineJob).all()

        assert len(jobs) == 1
        assert jobs[0].operation is PipelineOperation.RECLASSIFY
        assert jobs[0].status is PipelineJobStatus.PENDING
        assert dispatcher.triggers == 1


def test_auto_reclassify_is_debounced(engine):
    """
    Approving a cluster of 200 photos is one settling batch, not 200. The
    job runner permits one job at a time, so an undebounced trigger would
    build a backlog of identical passes.
    """
    with Session(engine) as session:
        dispatcher = FakeJobDispatcher()
        service = AutoReclassifyService(
            session, PipelineJobService(session), dispatcher
        )

        assert service.request() is True
        assert service.request() is False
        assert service.request() is False

        assert session.query(PipelineJob).count() == 1
        assert dispatcher.triggers == 1


def test_auto_reclassify_queues_again_once_the_previous_pass_finished(engine):
    with Session(engine) as session:
        job_service = PipelineJobService(session)
        dispatcher = FakeJobDispatcher()
        service = AutoReclassifyService(session, job_service, dispatcher)

        service.request()

        job = session.query(PipelineJob).one()
        job.status = PipelineJobStatus.COMPLETED
        session.commit()

        assert service.request() is True
        assert session.query(PipelineJob).count() == 2
        assert dispatcher.triggers == 2


def test_auto_reclassify_ignores_other_operations(engine):
    """
    A running sync says nothing about whether predictions are stale.
    """
    with Session(engine) as session:
        job_service = PipelineJobService(session)
        job_service.create_job(operation=PipelineOperation.SYNC)

        service = AutoReclassifyService(session, job_service, FakeJobDispatcher())

        assert service.request() is True
