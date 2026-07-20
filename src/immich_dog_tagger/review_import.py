from pathlib import Path
from dataclasses import dataclass
from immich_dog_tagger.services.learner import Learner


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
            )
            total += count
            identities[identity_dir.name] = count

        return ImportSummary(
            imported=total,
            identities=identities,
        )
