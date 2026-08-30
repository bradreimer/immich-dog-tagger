import { useCallback, useEffect, useMemo, useState } from "react";

import { IconArrowLeft, IconArrowRight, IconRefresh } from "@tabler/icons-react";
import { getDogs, getLibrary, getSettings } from "@/lib/api";
import type { LibraryQuery } from "@/lib/api";
import type { ClusterSort } from "@/types/clusters";
import type { Dog } from "@/types/dogs";
import type { LibraryEntry } from "@/types/library";
import { Button } from "@/components/ui/button";
import { LibraryDetailsPanel } from "./components/LibraryDetailsPanel";
import {
  LibraryFilters,
  type LibraryReviewedFilter,
  type LibrarySpeciesFilter,
} from "./components/LibraryFilters";
import { LibraryThumbnail } from "./components/LibraryThumbnail";
import { UndetectedPanel } from "./components/UndetectedPanel";

const PAGE_SIZE = 50;

interface Props {
  onNavigate: (path: string) => void;
}

export function LibraryPage({ onNavigate }: Props) {
  const [species, setSpecies] = useState<LibrarySpeciesFilter>("all");
  const [identity, setIdentity] = useState("");
  const [reviewedFilter, setReviewedFilter] = useState<LibraryReviewedFilter>("all");
  const [capturedAfter, setCapturedAfter] = useState("");
  const [capturedBefore, setCapturedBefore] = useState("");
  const [sort, setSort] = useState<ClusterSort>("captured_desc");

  const [dogs, setDogs] = useState<Dog[]>([]);
  const [immichUrl, setImmichUrl] = useState<string | null>(null);
  const [entries, setEntries] = useState<LibraryEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);

  useEffect(() => {
    getDogs({ includeInactive: false })
      .then(setDogs)
      .catch(() => setDogs([]));

    // The Immich deep link on the details panel is a convenience; failing
    // to read the configured URL must not take the grid down with it.
    getSettings()
      .then((settings) => setImmichUrl(settings.immich_external_url || null))
      .catch(() => setImmichUrl(null));
  }, []);

  const speciesIdentities = useMemo(
    () => (species === "all" ? dogs : dogs.filter((dog) => dog.species === species)),
    [dogs, species],
  );

  // A pet selected under one species no longer applies once the species
  // changes to something that doesn't include it.
  useEffect(() => {
    if (identity && !speciesIdentities.some((dog) => dog.name === identity)) {
      setIdentity("");
    }
  }, [identity, speciesIdentities]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);

    const query: LibraryQuery = {
      limit: PAGE_SIZE,
      offset,
      sort,
    };

    if (identity) {
      query.identity = identity;
    }

    if (species !== "all") {
      query.species = species;
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
      const page = await getLibrary(query);

      setEntries(page.items);
      setTotal(page.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load library");
    } finally {
      setLoading(false);
    }
  }, [identity, species, reviewedFilter, capturedAfter, capturedBefore, sort, offset]);

  useEffect(() => {
    load();
  }, [load]);

  // Any filter or sort change resets pagination -- a stale offset into a
  // differently-scoped or differently-ordered result set would otherwise
  // show an empty or misleading page.
  useEffect(() => {
    setOffset(0);
  }, [identity, species, reviewedFilter, capturedAfter, capturedBefore, sort]);

  // The selected photo only means something against the page it was
  // selected from -- clear it whenever that page changes.
  useEffect(() => {
    setSelectedId(null);
  }, [identity, species, reviewedFilter, capturedAfter, capturedBefore, sort, offset]);

  const selectedEntry =
    entries.find((entry) => entry.item.classification_id === selectedId) ?? null;

  const rangeStart = total === 0 ? 0 : offset + 1;
  const rangeEnd = Math.min(offset + PAGE_SIZE, total);

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <header className="space-y-2">
        <h1 className="text-3xl font-semibold tracking-tight">Library</h1>
        <p className="text-muted-foreground">
          Every classified photo, reviewed and unreviewed alike. Select one to see its
          details and fix it.
        </p>
      </header>

      <LibraryFilters
        species={species}
        onSpeciesChange={setSpecies}
        identity={identity}
        onIdentityChange={setIdentity}
        identities={speciesIdentities}
        reviewedFilter={reviewedFilter}
        onReviewedFilterChange={setReviewedFilter}
        capturedAfter={capturedAfter}
        onCapturedAfterChange={setCapturedAfter}
        capturedBefore={capturedBefore}
        onCapturedBeforeChange={setCapturedBefore}
        sort={sort}
        onSortChange={setSort}
      />

      {/*
        Shown while browsing library-wide, not scoped to one pet: a photo
        the detector missed has no identity yet, so it does not belong to
        any one pet's filter -- it is a library-wide gap (issue #147).
      */}
      {!identity && <UndetectedPanel identities={dogs} />}

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
        <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
              {entries.map((entry) => (
                <LibraryThumbnail
                  key={entry.item.classification_id}
                  entry={entry}
                  selected={entry.item.classification_id === selectedId}
                  onSelect={() => setSelectedId(entry.item.classification_id)}
                />
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
          </div>

          {selectedEntry && (
            <LibraryDetailsPanel
              entry={selectedEntry}
              immichUrl={immichUrl}
              onNavigate={onNavigate}
            />
          )}
        </div>
      )}
    </div>
  );
}

export default LibraryPage;
