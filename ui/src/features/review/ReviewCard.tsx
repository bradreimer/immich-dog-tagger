import type { ReviewItem } from "../../types/review";
import type { AssetRepairResult } from "../../types/photoLookup";
import { formatDate } from "../../lib/utils";

import { Card, CardContent } from "@/components/ui/card";
import { ImmichPhotoLink } from "./components/ImmichPhotoLink";
import { NotAnimalToggle } from "./components/NotAnimalToggle";
import { PhotoLookupLink } from "./components/PhotoLookupLink";
import { RepairButton } from "./components/RepairButton";
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
  /** Omitted in single-item mode (v1.11): there is no queue to skip past. */
  onSkip?: () => void;
  onToggleNotAnimal: () => void;
  onRepaired: (result: AssetRepairResult) => void;
  disabled: boolean;
}

export function ReviewCard({
  item,
  identities,
  immichUrl = null,
  onCorrect,
  onCorrectSpecies,
  onSkip,
  onToggleNotAnimal,
  onRepaired,
  disabled,
}: Props) {
  return (
    <section className="space-y-6">
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

        <RepairButton
          immichAssetId={item.immich_asset_id}
          onRepaired={onRepaired}
        />
      </div>

      {/* Image and its action panel side by side on desktop so the most-used
          controls (species, choose identity) are reachable without scrolling
          past the image -- see docs/specs/review-tab-engagement-and-layout.md.
          Columns stretch to the same row height (rather than top-aligning)
          so a short/wide image doesn't leave a gap below it -- see
          docs/specs/review-panel-space-efficiency.md. */}
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <ReviewImage cropId={item.crop_id} species={item.species} />

        <div className="space-y-3">
          <PredictionCard
            identity={item.prediction.identity}
            similarity={item.prediction.similarity}
            candidates={item.prediction.candidates}
            capturedAt={item.captured_at}
            onCorrect={onCorrect}
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

          {/* Wrong species / not-a-dog-or-cat are both low-frequency
              edge-case corrections, so they share one compact card instead
              of a full card each. */}
          <Card size="sm">
            <CardContent className="space-y-4">
              <SpeciesChooser
                species={item.species}
                onCorrectSpecies={onCorrectSpecies}
                disabled={disabled}
              />

              <NotAnimalToggle
                notAnimal={item.not_animal}
                onToggle={onToggleNotAnimal}
                disabled={disabled}
              />
            </CardContent>
          </Card>
        </div>
      </div>

      {item.suggestion && (
        <SimilarExample
          key={item.classification_id}
          exampleId={item.suggestion.example_id}
          identity={item.suggestion.identity}
          similarity={item.suggestion.similarity}
          capturedAt={item.suggestion.captured_at}
        />
      )}
    </section>
  );
}