from pathlib import Path
from dataclasses import dataclass
from immich_dog_tagger.services.learner import Learner


@dataclass(frozen=True)
class ImportPlan:
    identities: dict[str, int]

    @property
    def total(self) -> int:
        return sum(self.identities.values())


@dataclass(frozen=True)
class ImportSummary:
    imported: int
    identities: dict[str, int]


class ReviewImporter:
    def __init__(
        self,
        learner: Learner,
    ):
        self.learner = learner

    def import_confirmed(
        self,
        confirmed_dir: Path,
    ) -> ImportSummary:
        total = 0
        identities: dict[str, int] = {}

        for identity_dir in sorted(confirmed_dir.iterdir()):
            if not identity_dir.is_dir():
                continue

            count = self.learner.learn(
                identity_dir.name,
                identity_dir,
                source="review-confirmed",
            )

            total += count
            identities[identity_dir.name] = count

        return ImportSummary(
            imported=total,
            identities=identities,
        )

    def plan_import(
        self,
        confirmed_dir: Path,
    ) -> ImportPlan:
        identities = {}

        for identity_dir in sorted(confirmed_dir.iterdir()):
            if not identity_dir.is_dir():
                continue

            count = sum(1 for path in identity_dir.iterdir() if path.is_file())

            identities[identity_dir.name] = count

        return ImportPlan(
            identities=identities,
        )
