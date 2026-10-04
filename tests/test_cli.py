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
        def __init__(self, client, session, cache_dir=None, account_id=None):
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
        def __init__(self, client, session, cache_dir=None, account_id=None):
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


@pytest.mark.parametrize(
    ("command", "operation", "expected"),
    [
        ("reembed", PipelineOperation.REEMBED, "Examples re-embedded: 0"),
        ("reclassify", PipelineOperation.RECLASSIFY, "Confident: 0"),
    ],
)
def test_reembed_and_reclassify_run_through_job_runner(
    capsys, command, operation, expected
):
    with (
        patch("sys.argv", ["immich-dog-tagger", command]),
        patch("immich_dog_tagger.services.job_execution.get_embedder"),
    ):
        main()

    assert expected in capsys.readouterr().out

    engine = create_database(load_config().state_dir)

    with Session(engine) as session:
        jobs = session.query(PipelineJob).all()
        assert len(jobs) == 1
        assert jobs[0].operation is operation
        assert jobs[0].status is PipelineJobStatus.COMPLETED


@pytest.mark.parametrize(
    ("command", "service_path"),
    [
        ("reembed", "immich_dog_tagger.services.job_execution.ReembedService"),
        ("reclassify", "immich_dog_tagger.services.job_execution.ReclassifyService"),
    ],
)
def test_reembed_and_reclassify_failure_returns_nonzero(command, service_path):
    with (
        patch("sys.argv", ["immich-dog-tagger", command]),
        patch("immich_dog_tagger.services.job_execution.get_embedder"),
        patch(service_path, side_effect=RuntimeError("boom")),
        pytest.raises(SystemExit) as exc,
    ):
        main()

    assert exc.value.code == 1

    engine = create_database(load_config().state_dir)

    with Session(engine) as session:
        jobs = session.query(PipelineJob).all()
        assert len(jobs) == 1
        assert jobs[0].status is PipelineJobStatus.FAILED
        assert jobs[0].error_message == "boom"


class _FakeImmich:
    """Immich client double: one album holding a1, and no tags at all."""

    def __init__(self):
        self.tagged = []

    def list_albums(self):
        return [{"id": "album1", "albumName": "Dog - Fibs"}]

    def get_album_asset_ids(self, album_id):
        return {"a1"}

    def list_tags(self):
        return [{"id": "tag1", "name": "Dog - Fibs"}] if self.tagged else []

    def create_tag(self, name):
        return "tag1"

    def tag_assets(self, tag_id, asset_ids):
        self.tagged.extend(asset_ids)

    def get_tag_asset_ids(self, tag_id):
        return set(self.tagged)

    def add_assets_to_album(self, album_id, asset_ids):
        pass


def _seed_fibs(monkeypatch, tmp_path):
    from immich_dog_tagger.models import (
        Asset,
        Crop,
        CropClassification,
        Detection,
    )

    monkeypatch.chdir(tmp_path)
    engine = create_database(load_config().state_dir)

    with Session(engine) as session:
        asset = Asset(immich_asset_id="a1", checksum="c", extension=".jpg")
        detection = Detection(
            asset=asset, label="dog", confidence=1.0, x1=0, y1=0, x2=10, y2=10
        )
        crop = Crop(detection=detection, path="crop.jpg")
        session.add(CropClassification(crop=crop, identity="Fibs", confidence=0.95))
        session.commit()


def test_sync_audit_exits_nonzero_and_reports_drift(capsys, monkeypatch, tmp_path):
    _seed_fibs(monkeypatch, tmp_path)
    client = _FakeImmich()

    with (
        patch("immich_dog_tagger.cli.resolve_account"),
        patch("immich_dog_tagger.cli.build_immich_client", return_value=client),
        patch("sys.argv", ["immich-dog-tagger", "sync", "--audit"]),
        pytest.raises(SystemExit) as excinfo,
    ):
        main()

    assert excinfo.value.code == 1
    output = capsys.readouterr().out
    assert "dog/Fibs (1 expected): 1 missing tag" in output
    assert "sync --repair" in output
    assert client.tagged == []


def test_sync_repair_fixes_drift_and_a_second_audit_is_clean(
    capsys, monkeypatch, tmp_path
):
    _seed_fibs(monkeypatch, tmp_path)
    client = _FakeImmich()

    with (
        patch("immich_dog_tagger.cli.resolve_account"),
        patch("immich_dog_tagger.cli.build_immich_client", return_value=client),
    ):
        with patch("sys.argv", ["immich-dog-tagger", "sync", "--repair"]):
            main()

        assert client.tagged == ["a1"]
        assert "1 tag(s) added" in capsys.readouterr().out

        with patch("sys.argv", ["immich-dog-tagger", "sync", "--audit"]):
            main()

        assert "Immich matches state.db" in capsys.readouterr().out
