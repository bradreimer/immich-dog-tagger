import { useCallback, useEffect, useState } from "react";

import { IconArrowLeft, IconArrowRight, IconRefresh } from "@tabler/icons-react";
import { correctClassification, getLibrary } from "@/lib/api";
import type { LibraryQuery } from "@/lib/api";
import { Button } from "@/components/ui/button";
import type { LibraryEntry } from "@/types/library";
import { ClusterPanel } from "./components/ClusterPanel";
import { LibraryEntryCard } from "./components/LibraryEntryCard";
import { PetSelector } from "./components/PetSelector";
import { UndetectedPanel } from "./components/UndetectedPanel";
import { LibraryWorkspaceProvider } from "./LibraryWorkspaceProvider";
import { useLibraryWorkspace } from "./libraryWorkspace";

type ReviewedFilter = "all" | "reviewed" | "unreviewed";

const PAGE_SIZE = 24;

interface Props {
  onNavigate: (path: string) => void;
}

function LibraryWorkspaceView({ onNavigate }: Props) {
  const { species, identity, identities, selectedPet } = useLibraryWorkspace();

  const [entries, setEntries] = useState<LibraryEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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
  }, [identity, species, reviewedFilter, capturedAfter, capturedBefore, offset]);

  useEffect(() => {
    load();
  }, [load]);

  // Any selection or filter change resets pagination -- a stale offset into a
  // differently-scoped result set would otherwise show an empty or truncated
  // page.
  useEffect(() => {
    setOffset(0);
  }, [identity, species, reviewedFilter, capturedAfter, capturedBefore]);

  const correct = useCallback(async (classificationId: number, identityName: string) => {
    await correctClassification(classificationId, identityName);

    // Update in place rather than re-fetching the whole page, matching
    // ReviewPage's optimistic-update pattern after a correction.
    setEntries((current) =>
      current.map((entry) =>
        entry.item.classification_id === classificationId
          ? {
              ...entry,
              reviewed: true,
              reviewed_at: new Date().toISOString(),
              item: {
                ...entry.item,
                prediction: {
                  ...entry.item.prediction,
                  identity: identityName,
                  similarity: 1,
                },
              },
            }
          : entry,
      ),
    );
  }, []);

  const rangeStart = total === 0 ? 0 : offset + 1;
  const rangeEnd = Math.min(offset + PAGE_SIZE, total);

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <header className="space-y-2">
        <h1 className="text-3xl font-semibold tracking-tight">Library</h1>
        <p className="text-muted-foreground">
          {selectedPet
            ? `Every photo classified as ${selectedPet.name}, reviewed and unreviewed alike.`
            : "Pick a pet to work on one dog or cat at a time, or browse every classified photo."}
        </p>
      </header>

      <PetSelector onNavigate={onNavigate} />

      {selectedPet && (
        <ClusterPanel
          identity={selectedPet.name}
          species={selectedPet.species}
          onApproved={() => load()}
        />
      )}

      {/*
        Shown when no single pet is selected: a photo the detector missed
        has no identity yet, so it does not belong to any one pet's
        workspace -- it is a library-wide gap (issue #147).
      */}
      {!selectedPet && <UndetectedPanel identities={identities} />}

      <div className="flex flex-wrap items-center gap-3">
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
          {selectedPet
            ? `No photos classified as ${selectedPet.name} match these filters yet.`
            : "No classified photos match these filters yet."}
        </p>
      )}

      {!error && !loading && entries.length > 0 && (
        <>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6">
            {entries.map((entry) => (
              <LibraryEntryCard
                key={entry.item.classification_id}
                entry={entry}
                identities={identities}
                onCorrect={correct}
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
        </>
      )}
    </div>
  );
}

export function LibraryPage({ onNavigate }: Props) {
  return (
    <LibraryWorkspaceProvider>
      <LibraryWorkspaceView onNavigate={onNavigate} />
    </LibraryWorkspaceProvider>
  );
}

export default LibraryPage;
