import { useCallback, useEffect, useState } from "react";

import {
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


export function ReviewPage() {
  const [items, setItems] = useState<ReviewItem[]>([]);
  const [stats, setStats] = useState<ReviewQueueStats | null>(null);
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
      const [queue, queueStats] = await Promise.all([
        getReview(
          getReviewQuery(filter),
        ),
        getReviewStats(),
      ]);
      
      setItems(queue);
      setStats(queueStats);
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


  const skip = useCallback(
    async () => {
      const item = items[index];
      
      if (!item) {
        return;
      }
      
      setActionError(null);
      
      try {
        setSaving(true);

        await skipClassification(
          item.classification_id,
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
          : "Failed to save skip action",
        );
      } finally {
        setSaving(false);
      }
    },
    [items, index],
  );


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

  useReviewKeyboard({
    correct,
    skip,
    next,
    previous,
  });

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.target instanceof HTMLInputElement) {
        return;
      }
      
      switch (event.key.toLowerCase()) {
        case "arrowleft":
        previous();
        break;
        
        case "arrowright":
        next();
        break;
        
        case "s":
        skip();
        break;
        
        case "f":
        correct("Fibs");
        break;
        
        case "h":
        correct("Hermann");
        break;
        
        case "n":
        correct("Henri");
        break;
        
        case "u":
        correct("Unknown");
        break;
      }
    }
    
    window.addEventListener(
      "keydown",
      handleKeyDown,
    );
    
    return () => {
      window.removeEventListener(
        "keydown",
        handleKeyDown,
      );
    };
  }, [correct, next, previous, skip]);

  const item = items[index];

  if (loading) {
    return (
      <main className="mx-auto max-w-5xl p-6">
        <ReviewSkeleton />
      </main>
    );
  }

  if (error) {
    return (
      <main className="mx-auto max-w-5xl space-y-6 p-6">
        <h1>Review Error</h1>
        <p>{error}</p>
        
        <Button onClick={() => loadReview()}>
        Retry
        </Button>
      </main>
    );
  }

  if (!item) {
    return (
      <main className="mx-auto max-w-5xl p-6">
        <ReviewEmptyState
          onRefresh={() => loadReview()}
        />
      </main>
    );
  }

  return (
    <main className="container mx-auto max-w-6xl space-y-6 p-6">
    <header className="space-y-2">
      <h1 className="text-3xl font-bold tracking-tight">
        Dog Review
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
    Previous
    </Button>
    
    <Button
    variant="outline"
    onClick={next}
    disabled={index === items.length - 1}
    >
    Next
    </Button>
    </div>
    
    <KeyboardHints />
    </footer>
    </main>
  );
}


export default ReviewPage;