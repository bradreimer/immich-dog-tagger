import { useCallback, useEffect, useMemo, useState } from "react";

import { IconArrowLeft, IconArrowRight, IconRefresh } from "@tabler/icons-react";
import {
  ClassificationNotFoundError,
  getClassification,
  getDogs,
  correctClassification,
  correctSpecies,
  getReview,
  getReviewStats,
  getSettings,
  markCropNotAnimal,
  skipClassification,
  unmarkCropNotAnimal,
} from "../../lib/api";

import { Button } from "@/components/ui/button";
import { KeyboardHints } from "./components/KeyboardHints";
import { ReviewCard } from "./ReviewCard";
import { ReviewEmptyState } from "./components/ReviewEmptyState";
import { ReviewProgress } from "./components/ReviewProgress";
import { ReviewSkeleton } from "./components/ReviewSkeleton";
import { useReviewKeyboard } from "./hooks/useReviewKeyboard";
import type { ReviewFilter } from "./types";
import { getReviewQuery } from "./reviewFilters";

import type {
  ReviewItem,
  ReviewQueueStats,
} from "../../types/review";
import type { Dog } from "../../types/dogs";

/** Reads `?classification_id=` on initial load only -- this page doesn't
 * otherwise change the URL, so there's nothing to react to after mount. */
function classificationIdFromUrl(): number | null {
  const raw = new URLSearchParams(window.location.search).get("classification_id");

  if (!raw) {
    return null;
  }

  const id = Number(raw);

  return Number.isFinite(id) ? id : null;
}

/**
 * One arbitrary classification, edited by id (v1.11) -- the Library's Edit
 * link, not the active review queue. Same correction surface (ReviewCard),
 * no queue chrome: no Skip (there's nothing to skip past), no
 * Previous/Next-through-queue, no filter buttons, no progress bar.
 */
function ReviewSingleItemPage({ classificationId }: { classificationId: number }) {
  const [item, setItem] = useState<ReviewItem | null>(null);
  const [dogs, setDogs] = useState<Dog[]>([]);
  const [immichUrl, setImmichUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    setNotFound(false);

    try {
      const [loadedItem, dogItems, settings] = await Promise.all([
        getClassification(classificationId),
        getDogs({ includeInactive: false }).catch(() => []),
        getSettings().catch(() => null),
      ]);

      setItem(loadedItem);
      setDogs(dogItems);
      setImmichUrl(settings?.immich_external_url || null);
    } catch (err) {
      if (err instanceof ClassificationNotFoundError) {
        setNotFound(true);
      } else {
        setError(err instanceof Error ? err.message : "Failed to load photo");
      }
    } finally {
      setLoading(false);
    }
  }, [classificationId]);

  useEffect(() => {
    load();
  }, [load]);

  const correct = useCallback(
    async (identity: string) => {
      setActionError(null);

      try {
        setSaving(true);
        await correctClassification(classificationId, identity);
        setItem(await getClassification(classificationId));
      } catch (err) {
        setActionError(err instanceof Error ? err.message : "Failed to save correction");
      } finally {
        setSaving(false);
      }
    },
    [classificationId],
  );

  const correctSpeciesForItem = useCallback(
    async (species: "dog" | "cat") => {
      setActionError(null);

      try {
        setSaving(true);
        setItem(await correctSpecies(classificationId, species));
      } catch (err) {
        setActionError(err instanceof Error ? err.message : "Failed to correct species");
      } finally {
        setSaving(false);
      }
    },
    [classificationId],
  );

  const toggleNotAnimal = useCallback(async () => {
    if (!item) {
      return;
    }

    setActionError(null);

    try {
      setSaving(true);

      if (item.not_animal) {
        await unmarkCropNotAnimal(item.crop_id);
      } else {
        await markCropNotAnimal(item.crop_id);
      }

      setItem(await getClassification(classificationId));
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Failed to update");
    } finally {
      setSaving(false);
    }
  }, [item, classificationId]);

  if (loading) {
    return (
      <div className="mx-auto max-w-5xl">
        <ReviewSkeleton />
      </div>
    );
  }

  if (notFound) {
    return (
      <div className="mx-auto max-w-5xl space-y-4">
        <h1 className="text-3xl font-semibold tracking-tight">Photo not found</h1>
        <p className="text-muted-foreground">
          That classification doesn&apos;t exist.
        </p>
        <a
          href="/library"
          className="text-sm text-primary underline-offset-4 hover:underline"
        >
          Back to Library
        </a>
      </div>
    );
  }

  if (error || !item) {
    return (
      <div className="mx-auto max-w-5xl space-y-6">
        <h1 className="text-3xl font-semibold tracking-tight">Review Error</h1>
        <p className="text-muted-foreground">{error}</p>

        <Button onClick={() => load()}>
          <IconRefresh className="h-4 w-4" aria-hidden="true" />
          Retry
        </Button>
      </div>
    );
  }

  const speciesIdentities = dogs
    .filter((dog) => dog.species === item.species)
    .map((dog) => dog.name);

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <header className="space-y-2">
        <h1 className="text-3xl font-semibold tracking-tight">Editing photo</h1>
        <a
          href="/library"
          className="inline-flex items-center gap-1 text-sm text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
        >
          <IconArrowLeft className="h-4 w-4" aria-hidden="true" />
          Back to Library
        </a>
      </header>

      {actionError && <p className="text-sm text-destructive">{actionError}</p>}

      <ReviewCard
        item={item}
        identities={speciesIdentities}
        immichUrl={immichUrl}
        onCorrect={correct}
        onCorrectSpecies={correctSpeciesForItem}
        onToggleNotAnimal={toggleNotAnimal}
        disabled={saving}
      />
    </div>
  );
}

function ReviewQueuePage() {
  const [items, setItems] = useState<ReviewItem[]>([]);
  const [stats, setStats] = useState<ReviewQueueStats | null>(null);
  const [dogs, setDogs] = useState<Dog[]>([]);
  const [immichUrl, setImmichUrl] = useState<string | null>(null);
  const [index, setIndex] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [filter, setFilter] = useState<ReviewFilter>("all");
  const [saving, setSaving] = useState(false);


  const loadReview = useCallback(async () => {
    setLoading(true);
    setError(null);
    setActionError(null);

    try {
      const [queue, queueStats, dogItems, settings] = await Promise.all([
        getReview(
          getReviewQuery(filter),
        ),
        getReviewStats(),
        getDogs({ includeInactive: false }).catch(() => []),
        // The Immich deep link is a convenience; failing to read the
        // configured URL must not take the review queue down with it.
        getSettings().catch(() => null),
      ]);

      setItems(queue);
      setStats(queueStats);
      setDogs(dogItems);
      setImmichUrl(settings?.immich_external_url || null);
      setIndex(0);
    } catch (err) {
      setError(
        err instanceof Error
        ? err.message
        : "Failed to load review queue",
      );
    } finally {
      setLoading(false);
    }
  }, [filter]);

  const correct = useCallback(
    async (identity: string) => {
      const item = items[index];

      if (!item) {
        return;
      }

      setActionError(null);

      try {
        setSaving(true);

        await correctClassification(
          item.classification_id,
          identity,
        );

        setItems((current) => {
          const next = current.filter((_, i) => i !== index);

          setIndex((currentIndex) =>
            Math.min(currentIndex, next.length - 1),
          );

          return next;
        });

        setStats(await getReviewStats());
      } catch (err) {
        setActionError(
          err instanceof Error
          ? err.message
          : "Failed to save correction",
        );
      } finally {
        setSaving(false);
      }
    },
    [items, index],
  );


  const correctSpeciesForCurrentItem = useCallback(
    async (species: "dog" | "cat") => {
      const item = items[index];

      if (!item) {
        return;
      }

      setActionError(null);

      try {
        setSaving(true);

        const updated = await correctSpecies(
          item.classification_id,
          species,
        );

        setItems((current) =>
          current.map((existing, i) => (i === index ? updated : existing)),
        );

        setStats(await getReviewStats());
      } catch (err) {
        setActionError(
          err instanceof Error
          ? err.message
          : "Failed to correct species",
        );
      } finally {
        setSaving(false);
      }
    },
    [items, index],
  );


  const skip = useCallback(async () => {
    const item = items[index];
    if (!item) {
      return;
    }
    setActionError(null);
    try {
      setSaving(true);
      await skipClassification(item.classification_id);
      setItems((current) => {
        const next = current.filter((_, i) => i !== index);
        setIndex((currentIndex) => Math.min(currentIndex, next.length - 1));
        return next;
      });
      setStats(await getReviewStats());
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Failed to save skip action");
    } finally {
      setSaving(false);
    }
  }, [items, index]);

  const toggleNotAnimal = useCallback(async () => {
    const item = items[index];

    if (!item) {
      return;
    }

    setActionError(null);

    try {
      setSaving(true);

      if (item.not_animal) {
        await unmarkCropNotAnimal(item.crop_id);
      } else {
        await markCropNotAnimal(item.crop_id);
      }

      // Marking (or unmarking) settles the classification and records a
      // ReviewAction (issue #186) the same way Correct/Skip do, so the item
      // leaves the active queue the same way.
      setItems((current) => {
        const next = current.filter((_, i) => i !== index);
        setIndex((currentIndex) => Math.min(currentIndex, next.length - 1));
        return next;
      });

      setStats(await getReviewStats());
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Failed to update");
    } finally {
      setSaving(false);
    }
  }, [items, index]);


  const previous = useCallback(() => {
    setIndex((current) => Math.max(0, current - 1));
  }, []);


  const next = useCallback(() => {
    setIndex((current) =>
      Math.min(items.length - 1, current + 1),
  );
  }, [items.length]);


  useEffect(() => {
    loadReview();
  }, [loadReview]);

  const item = items[index];

  const speciesIdentities = item
    ? dogs.filter((dog) => dog.species === item.species).map((dog) => dog.name)
    : [];

  useReviewKeyboard({
    identities: speciesIdentities,
    correct,
    skip,
    next,
    previous,
  });

  if (loading) {
    return (
      <div className="mx-auto max-w-5xl">
        <ReviewSkeleton />
      </div>
    );
  }

  if (error) {
    return (
      <div className="mx-auto max-w-5xl space-y-6">
        <h1 className="text-3xl font-semibold tracking-tight">Review Error</h1>
        <p className="text-muted-foreground">{error}</p>

        <Button onClick={() => loadReview()}>
        <IconRefresh className="h-4 w-4" aria-hidden="true" />
        Retry
        </Button>
      </div>
    );
  }

  if (!item) {
    return (
      <div className="mx-auto max-w-5xl">
        <ReviewEmptyState
          onRefresh={() => loadReview()}
        />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl space-y-6">
    <header className="space-y-2">
      <h1 className="text-3xl font-semibold tracking-tight">
        {item.species === "cat" ? "Cat Review" : "Dog Review"}
      </h1>

      <div className="text-muted-foreground">
        {items.length > 0
          ? `${index + 1} of ${items.length} in current queue`
          : "Queue empty"}
      </div>

      <div className="flex flex-wrap gap-2">
        <Button
          variant={filter === "all" ? "default" : "outline"}
          onClick={() => setFilter("all")}
        >
          All
        </Button>

        <Button
          variant={filter === "unknown" ? "default" : "outline"}
          onClick={() => setFilter("unknown")}
        >
          Unknown
        </Button>

        <Button
          variant={
            filter === "low-confidence"
              ? "default"
              : "outline"
          }
          onClick={() =>
            setFilter("low-confidence")
          }
        >
          Low Confidence
        </Button>

        <Button
          variant={
            filter === "candidate-conflict"
              ? "default"
              : "outline"
          }
          onClick={() =>
            setFilter("candidate-conflict")
          }
        >
          Candidate Conflict
        </Button>
      </div>

      {stats && (
        <ReviewProgress
          reviewed={stats.reviewed}
          total={stats.total}
          remaining={stats.remaining}
        />
      )}
    </header>

    {actionError && (
      <p className="text-sm text-destructive">
      {actionError}
      </p>
    )}

    <ReviewCard
      item={item}
      identities={speciesIdentities}
      immichUrl={immichUrl}
      onCorrect={correct}
      onCorrectSpecies={correctSpeciesForCurrentItem}
      onSkip={skip}
      onToggleNotAnimal={toggleNotAnimal}
      disabled={saving}
    />

    <footer className="flex flex-col gap-3 text-sm text-muted-foreground">
    <div className="flex gap-2">
    <Button
      variant="outline"
      onClick={previous}
      disabled={index === 0}
    >
    <IconArrowLeft className="h-4 w-4" aria-hidden="true" />
    Previous
    </Button>

    <Button
    variant="outline"
    onClick={next}
    disabled={index === items.length - 1}
    >
    <IconArrowRight className="h-4 w-4" aria-hidden="true" />
    Next
    </Button>
    </div>

    <KeyboardHints />
    </footer>
    </div>
  );
}


export function ReviewPage() {
  const classificationId = useMemo(classificationIdFromUrl, []);

  if (classificationId !== null) {
    return <ReviewSingleItemPage classificationId={classificationId} />;
  }

  return <ReviewQueuePage />;
}


export default ReviewPage;
