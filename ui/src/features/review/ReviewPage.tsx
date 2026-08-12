import { useCallback, useEffect, useState } from "react";

import { IconArrowLeft, IconArrowRight, IconRefresh } from "@tabler/icons-react";
import {
  getDogs,
  correctClassification,
  getReview,
  getReviewStats,
  skipClassification,
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


export function ReviewPage() {
  const [items, setItems] = useState<ReviewItem[]>([]);
  const [stats, setStats] = useState<ReviewQueueStats | null>(null);
  const [dogs, setDogs] = useState<Dog[]>([]);
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
      const [queue, queueStats, dogItems] = await Promise.all([
        getReview(
          getReviewQuery(filter),
        ),
        getReviewStats(),
        getDogs({ includeInactive: false }).catch(() => []),
      ]);
      
      setItems(queue);
      setStats(queueStats);
      setDogs(dogItems);
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
      onCorrect={correct}
      onSkip={skip}
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


export default ReviewPage;