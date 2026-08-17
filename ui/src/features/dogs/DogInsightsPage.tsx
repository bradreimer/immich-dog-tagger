import { useEffect, useState } from "react";

import {
  IconArrowLeft,
  IconCalendarStats,
  IconClock,
  IconHeart,
  IconMapPin,
  IconPhoto,
  IconTrophy,
  IconUsers,
} from "@tabler/icons-react";
import {
  getInsightsCards,
  getInsightsPeople,
  getInsightsPlaces,
  getInsightsSummary,
  getInsightsTimeline,
} from "../../lib/api";
import type {
  InsightCard,
  InsightsSummary,
  PersonCount,
  PlaceCount,
  TimelineEntry,
} from "../../types/insights";

// One icon per category, not per specific insight -- so a new
// InsightProvider (ADR-005) appears here with no frontend change.
const CARD_ICONS: Record<InsightCard["category"], typeof IconPhoto> = {
  volume: IconPhoto,
  place: IconMapPin,
  social: IconUsers,
  milestone: IconTrophy,
  time: IconClock,
};
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { StatTile } from "@/components/ui/stat-tile";

interface Props {
  dogId: number;
  onNavigate: (path: string) => void;
}

function formatDate(value: string | null): string {
  if (!value) {
    return "—";
  }

  return new Date(value).toLocaleDateString();
}

export function DogInsightsPage({ dogId, onNavigate }: Props) {
  const [summary, setSummary] = useState<InsightsSummary | null>(null);
  const [places, setPlaces] = useState<PlaceCount[]>([]);
  const [people, setPeople] = useState<PersonCount[]>([]);
  const [timeline, setTimeline] = useState<TimelineEntry[]>([]);
  const [cards, setCards] = useState<InsightCard[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError(null);

      try {
        const [summaryData, placesData, peopleData, timelineData, cardsData] =
          await Promise.all([
            getInsightsSummary(dogId),
            getInsightsPlaces(dogId),
            getInsightsPeople(dogId),
            getInsightsTimeline(dogId, { limit: 25 }),
            getInsightsCards(dogId),
          ]);

        if (!cancelled) {
          setSummary(summaryData);
          setPlaces(placesData);
          setPeople(peopleData);
          setTimeline(timelineData);
          setCards(cardsData);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load insights");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    load();

    return () => {
      cancelled = true;
    };
  }, [dogId]);

  return (
    <section className="space-y-6">
      <header className="space-y-2">
        <Button variant="outline" onClick={() => onNavigate("/dogs")}>
          <IconArrowLeft className="h-4 w-4" aria-hidden="true" />
          Back to Dogs & Cats
        </Button>

        <h1 className="text-3xl font-semibold tracking-tight">
          {summary ? `${summary.identity_name}'s Insights` : "Insights"}
        </h1>
        <p className="text-muted-foreground">
          Simple counts derived from confirmed photos — not predictions, and not sent anywhere
          outside this app.
        </p>
      </header>

      {loading && <p className="text-sm text-muted-foreground">Loading…</p>}
      {error && <p className="text-sm text-destructive">{error}</p>}

      {!loading && !error && summary && summary.total_photos === 0 && (
        <Card>
          <CardContent>
            <p className="text-sm text-muted-foreground">
              No confirmed photos yet. Insights appear once this identity has been classified or
              reviewed in at least one photo.
            </p>
          </CardContent>
        </Card>
      )}

      {!loading && !error && summary && summary.total_photos > 0 && (
        <>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <StatTile
              icon={IconPhoto}
              tone="accent"
              label="Total photos"
              value={summary.total_photos}
            />
            <StatTile
              icon={IconCalendarStats}
              tone="info"
              label="First seen"
              value={formatDate(summary.first_seen)}
              subtext={`Last seen ${formatDate(summary.last_seen)}`}
            />
            <StatTile
              icon={IconMapPin}
              tone="good"
              label="Most photographed place"
              value={summary.top_place ? summary.top_place.label : "—"}
              subtext={
                summary.top_place ? `${summary.top_place.count} photo(s)` : "No location data yet"
              }
            />
            <StatTile
              icon={IconUsers}
              tone="warning"
              label="Most often photographed with"
              value={summary.top_person ? summary.top_person.label : "—"}
              subtext={
                summary.top_person
                  ? `${summary.top_person.count} photo(s) together`
                  : "No recognized people yet"
              }
            />
          </div>

          {summary.favorite_photo_count > 0 && (
            <p className="flex items-center gap-2 text-sm text-muted-foreground">
              <IconHeart className="h-4 w-4 text-status-serious" aria-hidden="true" />
              {summary.favorite_photo_count} of these photos are marked as favorites in Immich.
            </p>
          )}

          {cards.length > 0 && (
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              {cards.map((card) => (
                <StatTile
                  key={card.slug}
                  icon={CARD_ICONS[card.category]}
                  tone="accent"
                  label={card.title}
                  value={card.value}
                  subtext={card.subtext ?? undefined}
                />
              ))}
            </div>
          )}

          <div className="grid gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Places</CardTitle>
              </CardHeader>
              <CardContent>
                {places.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    No photos with location data yet.
                  </p>
                ) : (
                  <ul className="space-y-2">
                    {places.map((place) => (
                      <li
                        key={place.label}
                        className="flex items-center justify-between text-sm"
                      >
                        <span>{place.label}</span>
                        <span className="text-muted-foreground">{place.count} photo(s)</span>
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>People</CardTitle>
              </CardHeader>
              <CardContent>
                {people.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    No recognized people in these photos yet.
                  </p>
                ) : (
                  <ul className="space-y-2">
                    {people.map((person) => (
                      <li
                        key={person.person_id}
                        className="flex items-center justify-between text-sm"
                      >
                        <span>{person.label}</span>
                        <span className="text-muted-foreground">{person.count} photo(s)</span>
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Timeline</CardTitle>
            </CardHeader>
            <CardContent>
              {timeline.length === 0 ? (
                <p className="text-sm text-muted-foreground">No dated photos yet.</p>
              ) : (
                <ul className="space-y-2">
                  {timeline.map((entry) => (
                    <li
                      key={entry.asset_id}
                      className="flex items-center justify-between text-sm"
                    >
                      <span>{formatDate(entry.captured_at)}</span>
                      <span className="text-muted-foreground">
                        {[entry.city, entry.country].filter(Boolean).join(", ") || "Unknown location"}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </section>
  );
}
