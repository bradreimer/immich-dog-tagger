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
      setIndex((current) => current + 1);
    },
    [items, index],
  );


  useEffect(() => {
    loadReview();
  }, []);


  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.target instanceof HTMLInputElement) {
        return;
      }

      switch (event.key.toLowerCase()) {
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
  }, [correct]);


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

      <p>
        Keyboard:
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