from pathlib import Path

from immich_dog_tagger.review_import import ReviewImporter


class FakeLearner:
    def __init__(self):
        self.calls = []

    def learn(
        self,
        identity: str,
        directory: Path,
    ):
        self.calls.append((identity, directory))

        return 2


def test_import_confirmed(tmp_path):
    confirmed = tmp_path / "confirmed"

    (confirmed / "Fibs").mkdir(parents=True)
    (confirmed / "Hermann").mkdir()

    learner = FakeLearner()

    importer = ReviewImporter(learner)

    summary = importer.import_confirmed(confirmed)

    assert summary.imported == 4

    assert summary.identities == {
        "Fibs": 2,
        "Hermann": 2,
    }

    assert learner.calls == [
        ("Fibs", confirmed / "Fibs"),
        ("Hermann", confirmed / "Hermann"),
    ]


def test_import_confirmed_empty_directory(tmp_path):
    confirmed = tmp_path / "confirmed"
    confirmed.mkdir()

    learner = FakeLearner()

    importer = ReviewImporter(learner)

    summary = importer.import_confirmed(confirmed)

    assert summary.imported == 0
    assert summary.identities == {}
