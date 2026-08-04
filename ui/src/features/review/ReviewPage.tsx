import { useCallback, useEffect, useState } from "react";

import {
  correctClassification,
  getReview,
  getReviewStats,
  skipClassification,
} from "../../lib/api";

import { ReviewCard } from "./ReviewCard";
import { ReviewProgress } from "./components/ReviewProgress";
import { KeyboardHints } from "./components/KeyboardHints";
import { Button } from "@/components/ui/button";

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


  async function loadReview() {
    setLoading(true);
    setError(null);
    setActionError(null);

    try {
      const [queue, queueStats] = await Promise.all([
        getReview(),
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
  }
  

  const removeCurrentItem = useCallback(() => {
    setItems((current) => {
      const next = current.filter((_, i) => i !== index);

      setIndex((currentIndex) =>
        Math.min(currentIndex, next.length - 1),
      );

      return next;
    });
  }, [index]);


  const correct = useCallback(
    async (identity: string) => {
      const item = items[index];

      if (!item) {
        return;
      }

      setActionError(null);

      try {
        await correctClassification(
          item.classification_id,
          identity,
        );

        removeCurrentItem();

        setStats(await getReviewStats());
      } catch (err) {
        setActionError(
          err instanceof Error
            ? err.message
            : "Failed to save correction",
        );
      }
    },
    [items, index, removeCurrentItem],
  );


  const skip = useCallback(
    async () => {
      const item = items[index];

      if (!item) {
        return;
      }

      setActionError(null);

      try {
        await skipClassification(
          item.classification_id,
        );

        removeCurrentItem();

        setStats(await getReviewStats());
      } catch (err) {
        setActionError(
          err instanceof Error
            ? err.message
            : "Failed to save skip action",
        );
      }
    },
    [items, index, removeCurrentItem],
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
  }, []);


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
      <main>
        <h1>Loading review queue...</h1>
      </main>
    );
  }

  if (error) {
    return (
      <main>
        <h1>Review Error</h1>
        <p>{error}</p>

        <Button onClick={loadReview}>
          Retry
        </Button>
      </main>
    );
  }

  if (!item) {
    return (
      <main>
        <h1>Review Complete</h1>

        {stats && (
          <ReviewProgress
            reviewed={stats.reviewed}
            total={stats.total}
            remaining={stats.remaining}
          />
        )}

        <p>
          New detections will appear here after
          classification.
        </p>

        <Button onClick={loadReview}>
          Refresh
        </Button>
      </main>
    );
  }

    return (
    <main className="container mx-auto max-w-6xl space-y-6 p-6">
        <header className="space-y-2">
        <h1 className="text-3xl font-bold">
            Dog Review
        </h1>

        <div className="text-muted-foreground">
            {index + 1} of {items.length} in current queue
        </div>

        {stats && (
            <div className="text-sm text-muted-foreground">
            Reviewed {stats.reviewed} of {stats.total}
            {" "}
            · {stats.remaining} remaining
            </div>
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