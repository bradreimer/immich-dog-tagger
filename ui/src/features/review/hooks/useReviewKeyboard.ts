import { useEffect } from "react";

type ReviewKeyboardActions = {
  identities: string[];
  correct: (identity: string) => void;
  skip: () => void;
  next: () => void;
  previous: () => void;
};

export function useReviewKeyboard({
  identities,
  correct,
  skip,
  next,
  previous,
}: ReviewKeyboardActions) {
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
        case "1":
        case "2":
        case "3":
        case "4":
        case "5":
        case "6":
        case "7":
        case "8":
        case "9": {
          const index = Number.parseInt(event.key, 10) - 1;

          if (identities[index]) {
            correct(identities[index]);
          }

          break;
        }
      }
    }

    window.addEventListener("keydown", handleKeyDown);

    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [correct, identities, next, previous, skip]);
}