import { useEffect, useState } from "react";

import {
  correctClassification,
  getReview,
} from "./api";

import { ReviewCard } from "./ReviewCard";

import type { ReviewItem } from "./types";

function App() {
  const [item, setItem] = useState<ReviewItem | null>(null);

  async function loadReview() {
    const items = await getReview();

    setItem(
      items.length > 0
        ? items[0]
        : null,
    );
  }

  async function correct(identity: string) {
    if (!item) {
      return;
    }

    await correctClassification(
      item.classification_id,
      identity,
    );

    await loadReview();
  }

  useEffect(() => {
    loadReview();
  }, []);

  if (!item) {
    return (
      <main>
        <h1>No review items</h1>
      </main>
    );
  }

  return (
    <main>
      <h1>Dog Review</h1>

      <ReviewCard
        item={item}
        onCorrect={correct}
      />
    </main>
  );
}

export default App;