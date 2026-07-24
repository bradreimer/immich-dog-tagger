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
        patch("immich_dog_tagger.cli.OpenClipEmbedder"),
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
        patch("immich_dog_tagger.cli.OpenClipEmbedder"),
    ):
        main()

    output = capsys.readouterr().out

    assert "Limit: 25 items per stage" in output
