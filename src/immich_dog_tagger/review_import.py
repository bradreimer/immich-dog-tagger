from pathlib import Path
from dataclasses import dataclass
from immich_dog_tagger.media import is_supported_image
from immich_dog_tagger.models import EmbeddingSources
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
    skipped: int
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
        skipped = 0
        identities: dict[str, int] = {}

        if not confirmed_dir.exists():
            return ImportSummary(
                imported=0,
                skipped=0,
                identities={},
            )

        for identity_dir in sorted(confirmed_dir.iterdir()):
            if not identity_dir.is_dir():
                continue

            if identity_dir.name == "Unknown":
                continue

            images = [
                path
                for path in identity_dir.iterdir()
                if path.is_file() and is_supported_image(path)
            ]

            if not images:
                continue

            summary = self.learner.learn(
                identity_dir.name,
                identity_dir,
                source=EmbeddingSources.REVIEW,
            )

            total += summary.imported
            skipped += summary.skipped_existing
            identities[identity_dir.name] = summary.imported

        return ImportSummary(
            imported=total,
            skipped=skipped,
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

            if identity_dir.name == "Unknown":
                continue

            count = sum(
                1
                for path in identity_dir.iterdir()
                if path.is_file() and is_supported_image(path)
            )

            identities[identity_dir.name] = count

        return ImportPlan(
            identities=identities,
        )
