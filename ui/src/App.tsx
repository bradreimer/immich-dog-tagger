import { useCallback, useEffect, useState } from "react";

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

      setIndex(index + 1);
    },
    [items, index],
  );


  useEffect(() => {
    loadReview();
  }, []);


  useEffect(() => {
    function handleKey(
      event: KeyboardEvent,
    ) {
      switch (event.key) {
        case "1":
          correct("Fibs");
          break;

        case "2":
          correct("Hermann");
          break;

        case "3":
          correct("Henri");
          break;

        case "u":
        case "U":
          correct("Unknown");
          break;
      }
    }

    window.addEventListener(
      "keydown",
      handleKey,
    );

    return () => {
      window.removeEventListener(
        "keydown",
        handleKey,
      );
    };
  }, [correct]);


  const item = items[index];


  if (!item) {
    return (
      <main>
        <h1>
          No review items
        </h1>
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

      <p>
        1: Fibs | 2: Hermann | 3: Henri | U: Unknown
      </p>

      <ReviewCard
        item={item}
        onCorrect={correct}
      />
    </main>
  );
}


export default App;