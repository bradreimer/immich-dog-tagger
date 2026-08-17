"""
Derived pet insights (issue #94): favorite places, favorite people,
photo-count summaries, and a timeline -- computed at read time from
PetOccurrence + Asset facts, never stored as a conclusion (ADR-004).

All aggregation happens in Python over one identity's own occurrences,
which is bounded to a single pet's photo count -- not a library-wide scan.
Deterministic and explainable: every count here is directly re-derivable
from the rows that produced it.

Single-fact insights (favourite place/human, milestones, ...) are
determined by the pluggable InsightProvider mechanism in providers.py
(ADR-005); this service assembles the typed summary/places/people/timeline
responses that predate that mechanism, reusing the same aggregation
helpers so there is one computation behind each fact either way, and
orchestrates the provider registry for the generic cards() surface.
"""

from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from immich_dog_tagger.models import Identity, PetOccurrence

from .aggregations import PersonCount, PlaceCount, person_counts, place_counts
from .providers import INSIGHT_PROVIDERS, InsightCard, InsightContext


@dataclass(frozen=True)
class TimelineEntry:
    asset_id: int
    immich_asset_id: str
    captured_at: datetime | None
    city: str | None
    state: str | None
    country: str | None
    confidence: float
    source: str


@dataclass(frozen=True)
class InsightsSummary:
    identity_id: int
    identity_name: str
    total_photos: int
    first_seen: datetime | None
    last_seen: datetime | None
    photos_by_year: dict[int, int]
    top_place: PlaceCount | None
    top_person: PersonCount | None
    favorite_photo_count: int


class IdentityNotFoundError(ValueError):
    pass


class InsightsService:
    def __init__(self, session: Session):
        self.session = session

    def summary(self, identity_id: int) -> InsightsSummary:
        identity = self._require_identity(identity_id)
        occurrences = self._occurrences(identity_id)

        assets = [occurrence.asset for occurrence in occurrences]
        captured_dates = sorted(
            asset.captured_at for asset in assets if asset.captured_at is not None
        )

        years = Counter(
            asset.captured_at.year for asset in assets if asset.captured_at is not None
        )

        places = place_counts(assets)
        people = person_counts(assets)

        return InsightsSummary(
            identity_id=identity.id,
            identity_name=identity.name,
            total_photos=len(assets),
            first_seen=captured_dates[0] if captured_dates else None,
            last_seen=captured_dates[-1] if captured_dates else None,
            photos_by_year=dict(sorted(years.items())),
            top_place=places[0] if places else None,
            top_person=people[0] if people else None,
            favorite_photo_count=sum(1 for asset in assets if asset.is_favorite),
        )

    def timeline(
        self,
        identity_id: int,
        limit: int = 50,
        offset: int = 0,
    ) -> list[TimelineEntry]:
        self._require_identity(identity_id)
        occurrences = self._occurrences(identity_id)

        ordered = sorted(
            occurrences,
            key=lambda occurrence: (
                occurrence.asset.captured_at is None,
                occurrence.asset.captured_at,
            ),
        )

        page = ordered[offset : offset + limit]

        return [
            TimelineEntry(
                asset_id=occurrence.asset.id,
                immich_asset_id=occurrence.asset.immich_asset_id,
                captured_at=occurrence.asset.captured_at,
                city=occurrence.asset.city,
                state=occurrence.asset.state,
                country=occurrence.asset.country,
                confidence=occurrence.confidence,
                source=occurrence.source.value,
            )
            for occurrence in page
        ]

    def places(self, identity_id: int) -> list[PlaceCount]:
        self._require_identity(identity_id)
        occurrences = self._occurrences(identity_id)

        return place_counts([occurrence.asset for occurrence in occurrences])

    def people(self, identity_id: int) -> list[PersonCount]:
        self._require_identity(identity_id)
        occurrences = self._occurrences(identity_id)

        return person_counts([occurrence.asset for occurrence in occurrences])

    def cards(self, identity_id: int) -> list[InsightCard]:
        identity = self._require_identity(identity_id)
        occurrences = self._occurrences(identity_id)

        context = InsightContext(
            identity=identity,
            occurrences=occurrences,
            session=self.session,
            now=datetime.now(UTC),
        )

        cards = [provider.compute(context) for provider in INSIGHT_PROVIDERS]

        return [card for card in cards if card is not None]

    def _require_identity(self, identity_id: int) -> Identity:
        identity = self.session.get(Identity, identity_id)

        if identity is None:
            raise IdentityNotFoundError(f"Identity {identity_id} not found")

        return identity

    def _occurrences(self, identity_id: int) -> list[PetOccurrence]:
        return list(
            self.session.scalars(
                select(PetOccurrence)
                .where(PetOccurrence.identity_id == identity_id)
                .options(joinedload(PetOccurrence.asset))
            ).all()
        )
