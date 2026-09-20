import { useState } from "react";

import { IconArrowLeft, IconArrowRight } from "@tabler/icons-react";

import {
  correctClassification,
  correctSpecies,
  markCropNotAnimal,
  skipClassification,
  unmarkCropNotAnimal,
} from "../../../lib/api";
import type { AssetRepairResult } from "../../../types/photoLookup";
import type { ReviewGroup } from "../../../types/clusters";
import type { ReviewItem } from "../../../types/review";
import type { Dog } from "../../../types/dogs";

import { Button } from "@/components/ui/button";
import { ReviewCard } from "../ReviewCard";
import { useReviewKeyboard } from "../hooks/useReviewKeyboard";

interface Props {
  group: ReviewGroup;
  dogs: Dog[];
  immichUrl: string | null;
  showAccount?: boolean;
  /** Called after every settling action, so the Review tab's lifetime
   * `reviewed` stat (and its milestone celebration) stays accurate no
   * matter which mode produced the correction. */
  onReviewed: () => void;
  onDone: () => void;
}

/**
 * The "multiple dogs in this group?" escape hatch: rather than trusting a
 * grouping that turned out to be mixed, step through its members one at a
 * time with the exact same correction surface (`ReviewCard`) and keyboard
 * bindings (`useReviewKeyboard`) Queue mode already uses -- no new
 * vocabulary, no new write path.
 */
export function ReviewGroupSplitView({
  group,
  dogs,
  immichUrl,
  showAccount = false,
  onReviewed,
  onDone,
}: Props) {
  const [items, setItems] = useState<ReviewItem[]>(group.cluster.members);
  const [index, setIndex] = useState(0);
  const [saving, setSaving] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const removeCurrent = () => {
    setItems((current) => {
      const next = current.filter((_, i) => i !== index);
      setIndex((currentIndex) => Math.min(currentIndex, next.length - 1));
      return next;
    });
  };

  const correct = async (identity: string) => {
    const item = items[index];

    if (!item) {
      return;
    }

    setActionError(null);

    try {
      setSaving(true);
      await correctClassification(item.classification_id, identity);
      removeCurrent();
      onReviewed();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Failed to save correction");
    } finally {
      setSaving(false);
    }
  };

  const correctSpeciesForItem = async (species: "dog" | "cat") => {
    const item = items[index];

    if (!item) {
      return;
    }

    setActionError(null);

    try {
      setSaving(true);
      const updated = await correctSpecies(item.classification_id, species);
      setItems((current) => current.map((existing, i) => (i === index ? updated : existing)));
      onReviewed();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Failed to correct species");
    } finally {
      setSaving(false);
    }
  };

  const skip = async () => {
    const item = items[index];

    if (!item) {
      return;
    }

    setActionError(null);

    try {
      setSaving(true);
      await skipClassification(item.classification_id);
      removeCurrent();
      onReviewed();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Failed to save skip action");
    } finally {
      setSaving(false);
    }
  };

  const toggleNotAnimal = async () => {
    const item = items[index];

    if (!item) {
      return;
    }

    setActionError(null);

    try {
      setSaving(true);

      if (item.not_animal) {
        await unmarkCropNotAnimal(item.crop_id);
      } else {
        await markCropNotAnimal(item.crop_id);
      }

      removeCurrent();
      onReviewed();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Failed to update");
    } finally {
      setSaving(false);
    }
  };

  const handleRepaired = (_result: AssetRepairResult) => {
    removeCurrent();
    onReviewed();
  };

  const previous = () => setIndex((current) => Math.max(0, current - 1));
  const next = () => setIndex((current) => Math.min(items.length - 1, current + 1));

  const item = items[index];

  const speciesIdentities = item
    ? dogs.filter((dog) => dog.species === item.species).map((dog) => dog.name)
    : [];

  useReviewKeyboard({
    identities: speciesIdentities,
    correct,
    skip,
    next,
    previous,
  });

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Button variant="outline" onClick={onDone}>
          <IconArrowLeft className="h-4 w-4" aria-hidden="true" />
          Back to groups
        </Button>

        <span className="text-sm text-muted-foreground">
          {items.length > 0
            ? `Reviewing individually: ${index + 1} of ${items.length} in "${group.identity}"`
            : "Every photo in this group has been reviewed"}
        </span>
      </div>

      {actionError && <p className="text-sm text-destructive">{actionError}</p>}

      {item ? (
        <>
          <ReviewCard
            item={item}
            identities={speciesIdentities}
            immichUrl={immichUrl}
            showAccount={showAccount}
            onCorrect={correct}
            onCorrectSpecies={correctSpeciesForItem}
            onSkip={skip}
            onToggleNotAnimal={toggleNotAnimal}
            onRepaired={handleRepaired}
            disabled={saving}
          />

          <div className="flex gap-2">
            <Button variant="outline" onClick={previous} disabled={index === 0}>
              <IconArrowLeft className="h-4 w-4" aria-hidden="true" />
              Previous
            </Button>

            <Button variant="outline" onClick={next} disabled={index === items.length - 1}>
              <IconArrowRight className="h-4 w-4" aria-hidden="true" />
              Next
            </Button>
          </div>
        </>
      ) : (
        <Button onClick={onDone}>Back to groups</Button>
      )}
    </div>
  );
}
