from immich_dog_tagger.services.learner import LearnSummary
from immich_dog_tagger.review_import import ReviewImporter


class FakeLearner:
    def __init__(self):
        self.calls = []

    def learn(
        self,
        identity,
        directory,
        *,
        source="manual",
    ):
        self.calls.append(
            (
                identity,
                directory,
                source,
            )
        )

        return LearnSummary(
            imported=2,
            skipped_existing=0,
        )


class CountingLearner:
    def __init__(self):
        self.calls = 0

    def learn(self, identity, directory, *, source):
        self.calls += 1

        if self.calls == 1:
            return LearnSummary(
                imported=3,
                skipped_existing=0,
            )

        return LearnSummary(
            imported=0,
            skipped_existing=3,
        )


def test_import_confirmed(tmp_path):
    confirmed = tmp_path / "confirmed"

    fib_dir = confirmed / "Fibs"
    hermann_dir = confirmed / "Hermann"

    fib_dir.mkdir(parents=True)
    hermann_dir.mkdir()

    (fib_dir / "one.jpg").write_bytes(b"fake")
    (hermann_dir / "one.jpg").write_bytes(b"fake")

    learner = FakeLearner()

    importer = ReviewImporter(learner)

    summary = importer.import_confirmed(confirmed)

    assert summary.imported == 4

    assert summary.identities == {
        "Fibs": 2,
        "Hermann": 2,
    }

    assert learner.calls == [
        (
            "Fibs",
            confirmed / "Fibs",
            "review-confirmed",
        ),
        (
            "Hermann",
            confirmed / "Hermann",
            "review-confirmed",
        ),
    ]


def test_import_confirmed_empty_directory(tmp_path):
    confirmed = tmp_path / "confirmed"
    confirmed.mkdir()

    learner = FakeLearner()

    importer = ReviewImporter(learner)

    summary = importer.import_confirmed(confirmed)

    assert summary.imported == 0
    assert summary.identities == {}
    assert summary.skipped == 0


def test_plan_import(tmp_path):
    confirmed = tmp_path / "confirmed"

    fibs = confirmed / "Fibs"
    fibs.mkdir(parents=True)

    (fibs / "one.jpg").write_bytes(b"test")
    (fibs / "two.jpg").write_bytes(b"test")

    learner = FakeLearner()

    importer = ReviewImporter(learner)

    plan = importer.plan_import(confirmed)

    assert plan.total == 2
    assert plan.identities == {
        "Fibs": 2,
    }

    assert learner.calls == []


def test_import_confirmed_reports_skipped(tmp_path):
    confirmed = tmp_path / "confirmed"
    fibs = confirmed / "Fibs"
    fibs.mkdir(parents=True)

    (fibs / "dog.jpg").write_bytes(b"fake")

    learner = CountingLearner()
    importer = ReviewImporter(learner)

    first = importer.import_confirmed(confirmed)
    second = importer.import_confirmed(confirmed)

    assert first.imported == 3
    assert first.skipped == 0

    assert second.imported == 0
    assert second.skipped == 3


def test_plan_import_only_counts_images(tmp_path):
    confirmed = tmp_path / "confirmed"

    fibs = confirmed / "Fibs"
    fibs.mkdir(parents=True)

    (fibs / "dog.jpg").write_bytes(b"fake")
    (fibs / "notes.txt").write_text("ignore")

    plan = ReviewImporter(FakeLearner()).plan_import(confirmed)

    assert plan.identities == {
        "Fibs": 1,
    }
