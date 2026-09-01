from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from immich_dog_tagger.cli import main
from immich_dog_tagger.config import load_config
from immich_dog_tagger.database import create_database
from immich_dog_tagger.enums import PipelineJobStatus, PipelineOperation
from immich_dog_tagger.models import PipelineJob


def test_pipeline_dry_run_prints_plan(capsys):
    with (
        patch(
            "sys.argv",
            [
                "immich-dog-tagger",
                "pipeline",
                "--dry-run",
            ],
        ),
    ):
        main()

    output = capsys.readouterr().out

    assert "Pipeline dry run" in output
    assert "No changes made." in output


def test_pipeline_dry_run_with_limit(capsys):
    with (
        patch(
            "sys.argv",
            [
                "immich-dog-tagger",
                "pipeline",
                "--dry-run",
                "--limit",
                "25",
            ],
        ),
    ):
        main()

    output = capsys.readouterr().out

    assert "Limit: 25 items per stage" in output


def test_classify_accepts_all(capsys):
    with (
        patch(
            "sys.argv",
            [
                "immich-dog-tagger",
                "classify",
                "--all",
            ],
        ),
        patch("immich_dog_tagger.services.job_execution.get_embedder"),
    ):
        main()

    output = capsys.readouterr().out

    assert "Classified:" in output


def test_scan_runs_through_job_runner_and_persists_job(capsys):
    class FakeScanner:
        def __init__(self, client, session, cache_dir=None):
            pass

        def scan(self, limit=None, force=False, should_cancel=None):
            return 3

    with (
        patch(
            "sys.argv",
            [
                "immich-dog-tagger",
                "scan",
            ],
        ),
        patch("immich_dog_tagger.services.job_execution.Scanner", FakeScanner),
    ):
        main()

    output = capsys.readouterr().out

    assert "New assets: 3" in output

    engine = create_database(load_config().state_dir)

    with Session(engine) as session:
        jobs = session.query(PipelineJob).all()
        assert len(jobs) == 1
        assert jobs[0].operation is PipelineOperation.SCAN
        assert jobs[0].status is PipelineJobStatus.COMPLETED


def test_scan_failure_returns_nonzero_and_persists_failed_job():
    class FailingScanner:
        def __init__(self, client, session, cache_dir=None):
            pass

        def scan(self, limit=None, force=False, should_cancel=None):
            raise RuntimeError("scan exploded")

    with (
        patch(
            "sys.argv",
            [
                "immich-dog-tagger",
                "scan",
            ],
        ),
        patch(
            "immich_dog_tagger.services.job_execution.Scanner",
            FailingScanner,
        ),
        pytest.raises(SystemExit) as exc,
    ):
        main()

    assert exc.value.code == 1

    engine = create_database(load_config().state_dir)

    with Session(engine) as session:
        jobs = session.query(PipelineJob).all()
        assert len(jobs) == 1
        assert jobs[0].status is PipelineJobStatus.FAILED
        assert jobs[0].error_message == "scan exploded"


def test_status_outputs_learning_metrics(capsys, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    with patch(
        "sys.argv",
        [
            "immich-dog-tagger",
            "status",
        ],
    ):
        main()

    output = capsys.readouterr().out

    assert "Learning" in output
    assert "Examples by source:" in output
    assert "bootstrap:" in output
    assert "review:" in output
    assert "import:" in output
    assert "Review actions by type:" in output
    assert "skip:" in output
    assert "correct:" in output


def test_status_verbose_outputs_diagnostics(capsys, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    with patch(
        "sys.argv",
        [
            "immich-dog-tagger",
            "status",
            "--verbose",
        ],
    ):
        main()

    output = capsys.readouterr().out

    assert "Diagnostics" in output
    assert "download_failed:" in output


def test_help_does_not_expose_train_or_retrain_commands(capsys):
    with pytest.raises(SystemExit):
        main(["--help"])

    output = capsys.readouterr().out

    assert "train" not in output
    assert "retrain" not in output


def test_help_describes_learn_as_reference_example_import(capsys):
    with pytest.raises(SystemExit):
        main(["--help"])

    output = capsys.readouterr().out

    assert "reference examples" in output
