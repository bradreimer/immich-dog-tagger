import type { ReviewItem } from "../../types/review";

import { ReviewImage } from "./components/ReviewImage";
import { PredictionCard } from "./components/PredictionCard";
import { SimilarExample } from "./components/SimilarExample";
import { ReviewActions } from "./components/ReviewActions";
import { ReviewReason } from "./components/ReviewReason";

interface Props {
  item: ReviewItem;
  identities: string[];
  onCorrect: (identity: string) => void;
  onSkip: () => void;
  disabled: boolean;
}

export function ReviewCard({
  item,
  identities,
  onCorrect,
  onSkip,
  disabled,
}: Props) {
  return (
    <section className="space-y-8">
      <ReviewImage cropId={item.crop_id} />

      <ReviewReason reason={item.reason} />

      <ReviewActions
        identities={identities}
        onCorrect={onCorrect}
        onSkip={onSkip}
        disabled={disabled}
      />

      <div className="grid gap-6 lg:grid-cols-2">
        <PredictionCard
          identity={item.prediction.identity}
          similarity={item.prediction.similarity}
          candidates={item.prediction.candidates}
          onCorrect={onCorrect}
          disabled={disabled}
        />

        {item.suggestion && (
          <SimilarExample
            exampleId={item.suggestion.example_id}
            identity={item.suggestion.identity}
            similarity={item.suggestion.similarity}
            capturedAt={item.suggestion.captured_at}
          />
        )}
      </div>
    </section>
  );
}