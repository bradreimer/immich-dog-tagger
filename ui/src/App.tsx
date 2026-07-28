import { useCallback, useEffect, useState } from "react";

import {
  correctClassification,
  getReview,
  getReviewStats,
} from "./api";

import { ReviewCard } from "./ReviewCard";

import type {
  ReviewItem,
  ReviewQueueStats
} from "./types";


function App() {
  const [items, setItems] = useState<ReviewItem[]>([]);
  const [stats, setStats] = useState<ReviewQueueStats | null>(null);
  const [index, setIndex] = useState(0);
  const [loading, setLoading] = useState(true);


  async function loadReview() {
    setLoading(true);

    const [queue, queueStats] = await Promise.all([
      getReview(),
      getReviewStats(),
    ]);

    setItems(queue);
    setStats(queueStats);
    setIndex(0);

    setLoading(false);
  }


  const correct = useCallback(
    async (identity: string) => {
      const item = items[index];

      if (!item) {
        return;
      }

      await correctClassification(
        item.classification_id,
        identity,
      );

      const queueStats = await getReviewStats();

      setStats(queueStats);

      setIndex((current) =>
        Math.min(items.length - 1, current + 1),
      );
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
  }, [correct, next, previous]);

  const item = items[index];


  if (loading) {
    return (
      <main>
        <h1>Loading review queue...</h1>
      </main>
    );
  }


  if (!item) {
    return (
      <main>
        <h1>No review items</h1>

        <button onClick={loadReview}>
          Refresh
        </button>
      </main>
    );
  }


  return (
    <main>
      <h1>
        Dog Review
      </h1>

      <p>
        Current batch: {index + 1} / {items.length}
      </p>

      {stats && (
        <p>
          Reviewed: {stats.reviewed} / {stats.total}
          {" "}
          ({stats.remaining} remaining)
        </p>
      )}

      <div>
        <button
          onClick={previous}
          disabled={index === 0}
        >
          Previous
        </button>

        <button
          onClick={next}
          disabled={index === items.length - 1}
        >
          Next
        </button>
      </div>

      <p>
        Keyboard:
        {" "}
        ← = Previous,
        {" "}
        → = Next,
        {" "}
        F = Fibs,
        {" "}
        H = Hermann,
        {" "}
        N = Henri,
        {" "}
        U = Unknown
      </p>

      <ReviewCard
        item={item}
        onCorrect={correct}
      />
    </main>
  );
}


export default App;