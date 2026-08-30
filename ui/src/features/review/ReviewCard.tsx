import type { ReviewItem } from "../../types/review";
import { formatDate } from "../../lib/utils";

import { ImmichPhotoLink } from "./components/ImmichPhotoLink";
import { PhotoLookupLink } from "./components/PhotoLookupLink";
import { ReviewImage } from "./components/ReviewImage";
import { PredictionCard } from "./components/PredictionCard";
import { SimilarExample } from "./components/SimilarExample";
import { ReviewActions } from "./components/ReviewActions";
import { ReviewReason } from "./components/ReviewReason";
import { SpeciesChooser } from "./components/SpeciesChooser";

interface Props {
  item: ReviewItem;
  identities: string[];
  immichUrl?: string | null;
  onCorrect: (identity: string) => void;
  onCorrectSpecies: (species: "dog" | "cat") => void;
  onSkip: () => void;
  disabled: boolean;
}

export function ReviewCard({
  item,
  identities,
  immichUrl = null,
  onCorrect,
  onCorrectSpecies,
  onSkip,
  disabled,
}: Props) {
  return (
    <section className="space-y-8">
      <ReviewImage cropId={item.crop_id} />

      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <ReviewReason reason={item.reason} />

        <span className="text-sm text-muted-foreground">
          {formatDate(item.captured_at)}
        </span>

        <ImmichPhotoLink
          immichUrl={immichUrl}
          assetId={item.immich_asset_id}
        />

        <PhotoLookupLink assetId={item.immich_asset_id} />
      </div>

      <SpeciesChooser
        species={item.species}
        onCorrectSpecies={onCorrectSpecies}
        disabled={disabled}
      />

      <ReviewActions
        identities={identities}
        species={item.species}
        predictedIdentity={item.prediction.identity}
        onCorrect={onCorrect}
        onSkip={onSkip}
        disabled={disabled}
      />

      <div className="grid gap-6 lg:grid-cols-2">
        <PredictionCard
          identity={item.prediction.identity}
          similarity={item.prediction.similarity}
          candidates={item.prediction.candidates}
          capturedAt={item.captured_at}
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