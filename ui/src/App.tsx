import { useEffect, useState } from "react";

import {
  correctClassification,
  getReview,
} from "./api";

import { ReviewCard } from "./ReviewCard";

import type { ReviewItem } from "./types";


function App() {
  const [items, setItems] = useState<ReviewItem[]>([]);
  const [index, setIndex] = useState(0);


  async function loadReview() {
    const queue = await getReview();

    setItems(queue);
    setIndex(0);
  }


  async function correct(identity: string) {
    const item = items[index];

    if (!item) {
      return;
    }

    await correctClassification(
      item.classification_id,
      identity,
    );

    setIndex(index + 1);
  }


  useEffect(() => {
    loadReview();
  }, []);


  const item = items[index];


  if (!item) {
    return (
      <main>
        <h1>No review items</h1>
      </main>
    );
  }


  return (
    <main>
      <h1>
        Dog Review
      </h1>

      <p>
        {index + 1} / {items.length}
      </p>

      <ReviewCard
        item={item}
        onCorrect={correct}
      />
    </main>
  );
}


export default App;