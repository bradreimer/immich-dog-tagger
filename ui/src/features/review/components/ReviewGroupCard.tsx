import { useState } from "react";

import { IconUsersGroup } from "@tabler/icons-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { formatDate } from "@/lib/utils";

import type { ReviewGroup } from "../../../types/clusters";
import { useReviewKeyboard } from "../hooks/useReviewKeyboard";
import { IdentityChooser } from "./IdentityChooser";
import { ImmichPhotoLink } from "./ImmichPhotoLink";
import { NotAnimalToggle } from "./NotAnimalToggle";
import { ReviewReason } from "./ReviewReason";
import { SpeciesChooser } from "./SpeciesChooser";

interface Props {
  group: ReviewGroup;
  /** Every active identity of the group's species -- the same list Queue
   * mode's identity chooser offers for an item of that species. */
  identities: string[];
  /** Configured Immich base URL, for each member's "View in Immich" link. */
  immichUrl: string | null;
  /** Settle the selection as `identity`. The panel decides whether that is
   * an approval (the group's own identity) or a reassignment (any other). */
  onChooseIdentity: (identity: string, classificationIds: number[]) => void;
  onReject: (classificationIds: number[]) => void;
  onSkip: (classificationIds: number[]) => void;
  onCorrectSpecies: (species: "dog" | "cat", classificationIds: number[]) => void;
  onNotAnimal: (classificationIds: number[]) => void;
  /** "Multiple dogs in this group?" escape hatch (see spec): review every
   * member one at a time instead of trusting the grouping. */
  onSplit: () => void;
  onNext: () => void;
  onPrevious: () => void;
  disabled?: boolean;
}

/** "Jan 5, 2026 – Mar 2, 2027", a single date when equal, or null when no member is dated. */
function formatDateRange(earliest: string | null, latest: string | null): string | null {
  if (!earliest || !latest) {
    return null;
  }

  const first = formatDate(earliest);
  const last = formatDate(latest);

  return first === last ? first : `${first} – ${last}`;
}

/**
 * The one group Grouped mode shows at a time (see
 * docs/specs/review-grouped-focus-mode.md): large member thumbnails beside
 * the same action panel Queue mode's `ReviewCard` uses, with every action
 * applied to the selected members. Members start selected (the common case
 * is settling the whole group), except a member whose own top-ranked
 * prediction disagrees with the group's identity (`group.mismatches`, see
 * docs/specs/review-groups-temporal-spatial-refinement.md), which starts
 * deselected.
 */
export function ReviewGroupCard({
  group,
  identities,
  immichUrl,
  onChooseIdentity,
  onReject,
  onSkip,
  onCorrectSpecies,
  onNotAnimal,
  onSplit,
  onNext,
  onPrevious,
  disabled,
}: Props) {
  const { identity, species, cluster, mismatches } = group;

  const mismatchByMember = new Map(
    mismatches.map((mismatch) => [mismatch.classification_id, mismatch.reason]),
  );

  const [selected, setSelected] = useState<Set<number>>(
    () =>
      new Set(
        cluster.members
          .filter((member) => !mismatchByMember.has(member.classification_id))
          .map((member) => member.classification_id),
      ),
  );

  const toggleMember = (classificationId: number) => {
    setSelected((current) => {
      const next = new Set(current);

      if (next.has(classificationId)) {
        next.delete(classificationId);
      } else {
        next.add(classificationId);
      }

      return next;
    });
  };

  const selectAll = () =>
    setSelected(new Set(cluster.members.map((member) => member.classification_id)));

  const selectNone = () => setSelected(new Set());

  const selectedIds = cluster.members
    .map((member) => member.classification_id)
    .filter((id) => selected.has(id));

  const actionsDisabled = disabled || selectedIds.length === 0;

  const chooseIdentity = (chosen: string) => {
    if (!actionsDisabled) {
      onChooseIdentity(chosen, selectedIds);
    }
  };

  const skip = () => {
    if (!actionsDisabled) {
      onSkip(selectedIds);
    }
  };

  useReviewKeyboard({
    identities,
    correct: chooseIdentity,
    skip,
    next: onNext,
    previous: onPrevious,
  });

  const speciesLabel = species === "cat" ? "cats" : "dogs";

  const confidenceRange =
    cluster.min_similarity === cluster.max_similarity
      ? `${Math.round(cluster.max_similarity * 100)}%`
      : `${Math.round(cluster.min_similarity * 100)}%–${Math.round(cluster.max_similarity * 100)}%`;

  const dateRange = formatDateRange(
    cluster.earliest_captured_at,
    cluster.latest_captured_at,
  );

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <IconUsersGroup className="h-5 w-5 text-primary" aria-hidden="true" />
        <h2 className="text-lg font-semibold">{identity}</h2>
        <Badge variant="outline">{species}</Badge>
        <Badge variant="outline">{cluster.size} photos</Badge>
        <span className="text-sm text-muted-foreground">{confidenceRange} confidence</span>
        {dateRange && <span className="text-sm text-muted-foreground">{dateRange}</span>}
      </div>

      {/* Same two-column layout as ReviewCard: the photos on the left, the
          action panel on the right so it stays reachable without scrolling. */}
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
            <span>
              {selectedIds.length} of {cluster.size} selected
            </span>
            <Button variant="link" size="sm" onClick={selectAll} disabled={disabled}>
              Select all
            </Button>
            <Button variant="link" size="sm" onClick={selectNone} disabled={disabled}>
              Select none
            </Button>
          </div>

          <div className="grid grid-cols-[repeat(auto-fill,minmax(10rem,1fr))] gap-3">
            {cluster.members.map((member) => {
              const isSelected = selected.has(member.classification_id);
              const mismatchReason = mismatchByMember.get(member.classification_id);

              return (
                <div key={member.classification_id} className="flex flex-col items-center gap-1">
                  <button
                    type="button"
                    onClick={() => toggleMember(member.classification_id)}
                    disabled={disabled}
                    aria-pressed={isSelected}
                    aria-label={`${isSelected ? "Deselect" : "Select"} photo ${member.classification_id}`}
                    className={`w-full overflow-hidden rounded-md border-4 transition-opacity ${
                      isSelected ? "border-primary" : "border-transparent opacity-40"
                    }`}
                  >
                    <img
                      src={`/api/crops/${member.crop_id}`}
                      alt=""
                      loading="lazy"
                      decoding="async"
                      className="aspect-square w-full object-cover"
                    />
                  </button>

                  <ImmichPhotoLink immichUrl={immichUrl} assetId={member.immich_asset_id} />

                  {mismatchReason && <ReviewReason reason={mismatchReason} />}
                </div>
              );
            })}
          </div>
        </div>

        <div className="space-y-3">
          <p className="text-sm text-muted-foreground">
            Actions apply to the {selectedIds.length} selected photo
            {selectedIds.length === 1 ? "" : "s"}.
          </p>

          <IdentityChooser
            identities={identities}
            species={species}
            predictedIdentity={identity}
            onCorrect={chooseIdentity}
            onSkip={skip}
            disabled={actionsDisabled}
          />

          <Card size="sm">
            <CardContent className="space-y-4">
              <SpeciesChooser
                species={species}
                onCorrectSpecies={(chosen) => onCorrectSpecies(chosen, selectedIds)}
                disabled={actionsDisabled}
              />

              <NotAnimalToggle
                notAnimal={false}
                onToggle={() => onNotAnimal(selectedIds)}
                disabled={actionsDisabled}
              />

              <div className="space-y-2">
                <div className="text-sm font-medium">Wrong grouping?</div>

                <div className="flex flex-wrap gap-2">
                  <Button
                    variant="outline"
                    onClick={() => onReject(selectedIds)}
                    disabled={actionsDisabled}
                  >
                    Not {identity}
                  </Button>

                  <Button variant="outline" onClick={onSplit} disabled={disabled}>
                    Multiple {speciesLabel} here? Review individually
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </section>
  );
}
