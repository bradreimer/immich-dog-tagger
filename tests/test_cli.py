from unittest.mock import patch

from immich_dog_tagger.cli import main


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
        patch("immich_dog_tagger.cli.YOLODetector"),
        patch("immich_dog_tagger.cli.get_embedder"),
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
        patch("immich_dog_tagger.cli.YOLODetector"),
        patch("immich_dog_tagger.cli.get_embedder"),
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
        patch("immich_dog_tagger.cli.get_embedder"),
    ):
        main()

    output = capsys.readouterr().out

    assert "Classified:" in output


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
