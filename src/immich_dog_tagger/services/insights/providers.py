"""
Pluggable insight providers (ADR-005, docs/specs/v1.7-pluginable-insights.md).

Each InsightProvider computes one fun fact from an identity's PetOccurrence
rows joined to Asset -- the same read-time-only inputs InsightsService's
summary/places/people already use (ADR-004: never store a conclusion).
Adding a new insight means adding one class here and one line in
INSIGHT_PROVIDERS; nothing else in this package changes.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Literal, Protocol

from sqlalchemy.orm import Session

from immich_dog_tagger.models import Asset, Identity, PetOccurrence

from .aggregations import person_counts, place_counts

InsightCategory = Literal["volume", "place", "social", "milestone", "time"]


class InsightScope(str, Enum):
    IDENTITY = "identity"  # only needs this identity's own occurrences
    LIBRARY = "library"  # needs a cross-identity query (e.g. Best Friends)


@dataclass(frozen=True)
class InsightCard:
    slug: str
    title: str
    value: str
    subtext: str | None
    category: InsightCategory


@dataclass(frozen=True)
class InsightContext:
    identity: Identity
    occurrences: list[PetOccurrence]  # this identity's own, joined to Asset
    session: Session  # escape hatch for LIBRARY-scope providers only
    now: datetime  # injected, not datetime.now(), so time-based insights are testable

    @property
    def assets(self) -> list[Asset]:
        return [occurrence.asset for occurrence in self.occurrences]


class InsightProvider(Protocol):
    slug: str
    title: str
    category: InsightCategory
    scope: InsightScope

    def compute(self, context: InsightContext) -> InsightCard | None: ...


class FavouritePlaceProvider:
    slug = "favourite-place"
    title = "Favourite place"
    category: InsightCategory = "place"
    scope = InsightScope.IDENTITY

    def compute(self, context: InsightContext) -> InsightCard | None:
        places = place_counts(context.assets)

        if not places:
            return None

        top = places[0]

        return InsightCard(
            slug=self.slug,
            title=self.title,
            value=top.label,
            subtext=f"{top.count} photo(s)",
            category=self.category,
        )


class FavouriteHumanProvider:
    slug = "favourite-human"
    title = "Favourite human"
    category: InsightCategory = "social"
    scope = InsightScope.IDENTITY

    def compute(self, context: InsightContext) -> InsightCard | None:
        people = person_counts(context.assets)

        if not people:
            return None

        top = people[0]

        return InsightCard(
            slug=self.slug,
            title=self.title,
            value=top.label,
            subtext=f"{top.count} photo(s) together",
            category=self.category,
        )


class ImmichFavoritesProvider:
    slug = "immich-favorites"
    title = "Immich favorites"
    category: InsightCategory = "volume"
    scope = InsightScope.IDENTITY

    def compute(self, context: InsightContext) -> InsightCard | None:
        count = sum(1 for asset in context.assets if asset.is_favorite)

        if count == 0:
            return None

        return InsightCard(
            slug=self.slug,
            title=self.title,
            value=str(count),
            subtext="marked as favorites in Immich",
            category=self.category,
        )


class TotalPhotosMilestoneProvider:
    """
    The most recently crossed round-number confirmed-photo count (e.g. "this
    was Hermann's 1000th confirmed photo"), per docs/specs/v1.7-pluginable-insights.md.
    Computed entirely from existing PetOccurrence/Asset data -- no schema change.
    """

    slug = "milestone-total-photos"
    title = "Milestone"
    category: InsightCategory = "milestone"
    scope = InsightScope.IDENTITY

    thresholds = (100, 500, 1000, 5000, 10000)

    def compute(self, context: InsightContext) -> InsightCard | None:
        reached = [t for t in self.thresholds if len(context.occurrences) >= t]

        if not reached:
            return None

        threshold = reached[-1]

        ordered = sorted(
            context.occurrences,
            key=lambda occurrence: (
                occurrence.asset.captured_at is None,
                occurrence.asset.captured_at,
            ),
        )
        milestone_asset = ordered[threshold - 1].asset

        subtext = (
            milestone_asset.captured_at.strftime("%B %Y")
            if milestone_asset.captured_at
            else "date unknown"
        )

        return InsightCard(
            slug=self.slug,
            title=self.title,
            value=f"{threshold:,}th confirmed photo",
            subtext=subtext,
            category=self.category,
        )


INSIGHT_PROVIDERS: list[InsightProvider] = [
    FavouritePlaceProvider(),
    FavouriteHumanProvider(),
    ImmichFavoritesProvider(),
    TotalPhotosMilestoneProvider(),
]
