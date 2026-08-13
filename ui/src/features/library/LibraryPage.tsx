import { useCallback, useEffect, useState } from "react";

import { IconArrowLeft, IconArrowRight, IconRefresh } from "@tabler/icons-react";
import { getDogs, getLibrary } from "@/lib/api";
import type { LibraryQuery } from "@/lib/api";
import { Button } from "@/components/ui/button";
import type { Dog } from "@/types/dogs";
import type { LibraryEntry } from "@/types/library";
import { LibraryEntryCard } from "./components/LibraryEntryCard";

type SpeciesFilter = "all" | "dog" | "cat";
type ReviewedFilter = "all" | "reviewed" | "unreviewed";

const PAGE_SIZE = 24;

export function LibraryPage() {
  const [entries, setEntries] = useState<LibraryEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [dogs, setDogs] = useState<Dog[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [identityFilter, setIdentityFilter] = useState("");
  const [speciesFilter, setSpeciesFilter] = useState<SpeciesFilter>("all");
  const [reviewedFilter, setReviewedFilter] = useState<ReviewedFilter>("all");
  const [capturedAfter, setCapturedAfter] = useState("");
  const [capturedBefore, setCapturedBefore] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);

    const query: LibraryQuery = {
      limit: PAGE_SIZE,
      offset,
    };

    if (identityFilter) {
      query.identity = identityFilter;
    }

    if (speciesFilter !== "all") {
      query.species = speciesFilter;
    }

    if (reviewedFilter !== "all") {
      query.reviewed = reviewedFilter === "reviewed";
    }

    if (capturedAfter) {
      query.captured_after = `${capturedAfter}T00:00:00`;
    }

    if (capturedBefore) {
      query.captured_before = `${capturedBefore}T23:59:59`;
    }

    try {
      const [page, dogItems] = await Promise.all([
        getLibrary(query),
        getDogs({ includeInactive: false }).catch(() => []),
      ]);

      setEntries(page.items);
      setTotal(page.total);
      setDogs(dogItems);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load library");
    } finally {
      setLoading(false);
    }
  }, [identityFilter, speciesFilter, reviewedFilter, capturedAfter, capturedBefore, offset]);

  useEffect(() => {
    load();
  }, [load]);

  // Any filter change resets pagination -- a stale offset into a
  // differently-filtered result set would otherwise show an empty or
  // truncated page.
  useEffect(() => {
    setOffset(0);
  }, [identityFilter, speciesFilter, reviewedFilter, capturedAfter, capturedBefore]);

  const identities = dogs
    .filter((dog) => speciesFilter === "all" || dog.species === speciesFilter)
    .map((dog) => dog.name);

  const rangeStart = total === 0 ? 0 : offset + 1;
  const rangeEnd = Math.min(offset + PAGE_SIZE, total);

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <header className="space-y-2">
        <h1 className="text-3xl font-semibold tracking-tight">Library</h1>
        <p className="text-muted-foreground">
          Every classified photo, reviewed and unreviewed alike -- browse, filter, and search
          your tagged library.
        </p>
      </header>

      <div className="flex flex-wrap items-center gap-3">
        <select
          value={identityFilter}
          onChange={(event) => setIdentityFilter(event.target.value)}
          className="h-10 rounded-md border border-input bg-background px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
          aria-label="Filter by identity"
        >
          <option value="">All identities</option>
          {identities.map((name) => (
            <option key={name} value={name}>
              {name}
            </option>
          ))}
        </select>

        <div className="flex gap-2" role="group" aria-label="Filter by species">
          {(["all", "dog", "cat"] as const).map((option) => (
            <Button
              key={option}
              type="button"
              variant={speciesFilter === option ? "default" : "outline"}
              onClick={() => setSpeciesFilter(option)}
            >
              {option === "all" ? "All species" : option === "dog" ? "Dogs" : "Cats"}
            </Button>
          ))}
        </div>

        <div className="flex gap-2" role="group" aria-label="Filter by review status">
          {(["all", "reviewed", "unreviewed"] as const).map((option) => (
            <Button
              key={option}
              type="button"
              variant={reviewedFilter === option ? "default" : "outline"}
              onClick={() => setReviewedFilter(option)}
            >
              {option === "all" ? "All" : option === "reviewed" ? "Reviewed" : "Unreviewed"}
            </Button>
          ))}
        </div>

        <label className="flex items-center gap-2 text-sm text-muted-foreground">
          Captured after
          <input
            type="date"
            value={capturedAfter}
            onChange={(event) => setCapturedAfter(event.target.value)}
            className="h-10 rounded-md border border-input bg-background px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
          />
        </label>

        <label className="flex items-center gap-2 text-sm text-muted-foreground">
          Captured before
          <input
            type="date"
            value={capturedBefore}
            onChange={(event) => setCapturedBefore(event.target.value)}
            className="h-10 rounded-md border border-input bg-background px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
          />
        </label>
      </div>

      {error && (
        <div className="space-y-3">
          <p className="text-sm text-destructive">{error}</p>
          <Button onClick={() => load()}>
            <IconRefresh className="h-4 w-4" aria-hidden="true" />
            Retry
          </Button>
        </div>
      )}

      {!error && loading && (
        <p className="text-sm text-muted-foreground">Loading library…</p>
      )}

      {!error && !loading && entries.length === 0 && (
        <p className="text-sm text-muted-foreground">
          No classified photos match these filters yet.
        </p>
      )}

      {!error && !loading && entries.length > 0 && (
        <>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6">
            {entries.map((entry) => (
              <LibraryEntryCard key={entry.item.classification_id} entry={entry} />
            ))}
          </div>

          <div className="flex items-center justify-between text-sm text-muted-foreground">
            <span>
              {rangeStart}-{rangeEnd} of {total}
            </span>

            <div className="flex gap-2">
              <Button
                variant="outline"
                onClick={() => setOffset((current) => Math.max(0, current - PAGE_SIZE))}
                disabled={offset === 0}
              >
                <IconArrowLeft className="h-4 w-4" aria-hidden="true" />
                Previous
              </Button>

              <Button
                variant="outline"
                onClick={() => setOffset((current) => current + PAGE_SIZE)}
                disabled={offset + PAGE_SIZE >= total}
              >
                <IconArrowRight className="h-4 w-4" aria-hidden="true" />
                Next
              </Button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

export default LibraryPage;
