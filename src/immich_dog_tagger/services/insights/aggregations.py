"""
Shared read-time aggregation helpers over Asset facts. Used by both
InsightsService's typed summary/places/people methods and the InsightProvider
implementations in providers.py, so there is exactly one computation behind
each fact regardless of which surface reads it (ADR-005).
"""

from collections import Counter
from dataclasses import dataclass

from immich_dog_tagger.models import Asset


@dataclass(frozen=True)
class PlaceCount:
    city: str | None
    state: str | None
    country: str | None
    count: int

    @property
    def label(self) -> str:
        parts = [part for part in (self.city, self.state, self.country) if part]
        return ", ".join(parts) if parts else "Unknown location"


@dataclass(frozen=True)
class PersonCount:
    person_id: str
    name: str | None
    count: int

    @property
    def label(self) -> str:
        return self.name or self.person_id


def place_counts(assets: list[Asset]) -> list[PlaceCount]:
    keyed = [
        (asset.city, asset.state, asset.country)
        for asset in assets
        if asset.city or asset.state or asset.country
    ]

    counts = Counter(keyed)

    return [
        PlaceCount(city=city, state=state, country=country, count=count)
        for (city, state, country), count in counts.most_common()
    ]


def person_counts(assets: list[Asset]) -> list[PersonCount]:
    # Keyed by person_id alone, not (id, name) -- a renamed Immich person
    # shouldn't be double-counted as two different people.
    counts: Counter[str] = Counter()
    names: dict[str, str | None] = {}

    for asset in assets:
        seen_in_asset: set[str] = set()

        for person in asset.people:
            person_id = person.get("id")

            if not person_id or person_id in seen_in_asset:
                continue

            seen_in_asset.add(person_id)
            counts[person_id] += 1
            names[person_id] = person.get("name") or names.get(person_id)

    return [
        PersonCount(person_id=person_id, name=names.get(person_id), count=count)
        for person_id, count in counts.most_common()
    ]
