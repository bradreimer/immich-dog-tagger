import { useEffect } from "react";

type ReviewKeyboardActions = {
  correct: (identity: string) => void;
  skip: () => void;
  next: () => void;
  previous: () => void;
};

export function useReviewKeyboard({
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

    window.addEventListener("keydown", handleKeyDown);

    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [correct, next, previous, skip]);
}