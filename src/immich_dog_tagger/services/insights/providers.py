"""
Pluggable insight providers (ADR-005, docs/specs/v1.7-pluginable-insights.md).

Each InsightProvider computes one fun fact from an identity's PetOccurrence
rows joined to Asset -- the same read-time-only inputs InsightsService's
summary/places/people already use (ADR-004: never store a conclusion).
Adding a new insight means adding one class here and one line in
INSIGHT_PROVIDERS; nothing else in this package changes.
"""

import calendar
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from itertools import pairwise
from typing import Literal, Protocol

from sqlalchemy import select
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


class MostActiveMonthProvider:
    """The single calendar month with the most confirmed photos (#269)."""

    slug = "most-active-month"
    title = "Most active month"
    category: InsightCategory = "time"
    scope = InsightScope.IDENTITY

    def compute(self, context: InsightContext) -> InsightCard | None:
        months = Counter(
            (occurrence.asset.captured_at.year, occurrence.asset.captured_at.month)
            for occurrence in context.occurrences
            if occurrence.asset.captured_at is not None
        )

        if not months:
            return None

        (year, month), count = months.most_common(1)[0]

        return InsightCard(
            slug=self.slug,
            title=self.title,
            value=f"{calendar.month_name[month]} {year}",
            subtext=f"{count} photo(s)",
            category=self.category,
        )


class LongestStreakProvider:
    """
    Longest run of consecutive days with at least one confirmed photo (#269).
    Below a 2-day run there's nothing worth calling a "streak".
    """

    slug = "longest-streak"
    title = "Longest streak"
    category: InsightCategory = "time"
    scope = InsightScope.IDENTITY

    def compute(self, context: InsightContext) -> InsightCard | None:
        dates = sorted(
            {
                occurrence.asset.captured_at.date()
                for occurrence in context.occurrences
                if occurrence.asset.captured_at is not None
            }
        )

        if len(dates) < 2:
            return None

        best_start = dates[0]
        best_length = 1
        run_start = dates[0]
        run_length = 1

        for previous, current in pairwise(dates):
            if (current - previous).days == 1:
                run_length += 1
            else:
                run_start = current
                run_length = 1

            if run_length > best_length:
                best_length = run_length
                best_start = run_start

        if best_length < 2:
            return None

        best_end = best_start + timedelta(days=best_length - 1)

        return InsightCard(
            slug=self.slug,
            title=self.title,
            value=f"{best_length} days",
            subtext=(
                f"{best_start.strftime('%B %d, %Y')} - {best_end.strftime('%B %d, %Y')}"
            ),
            category=self.category,
        )


class BestFriendProvider:
    """
    The other identity (dog or cat) this one co-occurs with most often in the
    same confirmed photos (v1.6/v1.7's deferred "Best Friends" item; the
    first real user of the LIBRARY scope InsightContext reserves for it).
    Ties break on the lower identity_id, matching the deterministic-but-
    arbitrary tiebreak Counter.most_common() already gives place/person
    counts elsewhere in this package.
    """

    slug = "best-friend"
    title = "Best friend"
    category: InsightCategory = "social"
    scope = InsightScope.LIBRARY

    def compute(self, context: InsightContext) -> InsightCard | None:
        asset_ids = {occurrence.asset_id for occurrence in context.occurrences}

        if not asset_ids:
            return None

        rows = context.session.execute(
            select(PetOccurrence.identity_id, Identity.name)
            .join(Identity, Identity.id == PetOccurrence.identity_id)
            .where(
                PetOccurrence.asset_id.in_(asset_ids),
                PetOccurrence.identity_id != context.identity.id,
            )
        ).all()

        if not rows:
            return None

        counts: Counter[int] = Counter(identity_id for identity_id, _ in rows)
        names = dict(rows)

        best_identity_id, count = min(
            counts.items(), key=lambda item: (-item[1], item[0])
        )

        return InsightCard(
            slug=self.slug,
            title=self.title,
            value=names[best_identity_id],
            subtext=f"{count} photo(s) together",
            category=self.category,
        )


class YearOverYearProvider:
    """
    Confirmed-photo count this calendar year vs. last (#269). None when the
    prior year has zero confirmed photos -- "+N vs. 0" would read as a
    manufactured comparison rather than a real one.
    """

    slug = "year-over-year"
    title = "Year over year"
    category: InsightCategory = "volume"
    scope = InsightScope.IDENTITY

    def compute(self, context: InsightContext) -> InsightCard | None:
        years = Counter(
            occurrence.asset.captured_at.year
            for occurrence in context.occurrences
            if occurrence.asset.captured_at is not None
        )

        previous_count = years.get(context.now.year - 1, 0)

        if previous_count == 0:
            return None

        current_count = years.get(context.now.year, 0)
        delta = current_count - previous_count
        sign = "+" if delta >= 0 else "-"

        return InsightCard(
            slug=self.slug,
            title=self.title,
            value=f"{sign}{abs(delta)} photo(s) vs. last year",
            subtext=f"{current_count} this year, {previous_count} last year",
            category=self.category,
        )


INSIGHT_PROVIDERS: list[InsightProvider] = [
    FavouritePlaceProvider(),
    FavouriteHumanProvider(),
    ImmichFavoritesProvider(),
    TotalPhotosMilestoneProvider(),
    MostActiveMonthProvider(),
    LongestStreakProvider(),
    BestFriendProvider(),
    YearOverYearProvider(),
]
