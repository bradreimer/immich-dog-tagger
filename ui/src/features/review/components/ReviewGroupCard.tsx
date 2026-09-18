import { useState } from "react";

import { IconUsersGroup } from "@tabler/icons-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

import type { ReviewGroup } from "../../../types/clusters";

interface Props {
  group: ReviewGroup;
  onApprove: (classificationIds: number[]) => void;
  onReject: (classificationIds: number[]) => void;
  /** "Multiple dogs in this group?" escape hatch (see spec): review every
   * member one at a time instead of trusting the grouping. */
  onSplit: () => void;
  disabled?: boolean;
}

/**
 * One group in the Review tab's Grouped mode: a batch of visually similar
 * pending photos the classifier already put forward for the same identity.
 * Members start selected (the common case is approving the whole group);
 * deselecting the odd photo out is the exception path, matching v1.8 FR-4's
 * convention for the Library's cluster cards.
 */
export function ReviewGroupCard({ group, onApprove, onReject, onSplit, disabled }: Props) {
  const { identity, species, cluster } = group;

  const [selected, setSelected] = useState<Set<number>>(
    () => new Set(cluster.members.map((member) => member.classification_id)),
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

  const speciesLabel = species === "cat" ? "cats" : "dogs";

  const confidenceRange =
    cluster.min_similarity === cluster.max_similarity
      ? `${Math.round(cluster.max_similarity * 100)}%`
      : `${Math.round(cluster.min_similarity * 100)}%–${Math.round(cluster.max_similarity * 100)}%`;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex flex-wrap items-center gap-2">
          <IconUsersGroup className="h-5 w-5 text-primary" aria-hidden="true" />
          {identity}
          <Badge variant="outline">{species}</Badge>
          <Badge variant="outline">{cluster.size} photos</Badge>
          <span className="text-sm font-normal text-muted-foreground">
            {confidenceRange} confidence
          </span>
        </CardTitle>
      </CardHeader>

      <CardContent className="space-y-4">
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

        <div className="flex flex-wrap gap-2">
          {cluster.members.map((member) => {
            const isSelected = selected.has(member.classification_id);

            return (
              <button
                key={member.classification_id}
                type="button"
                onClick={() => toggleMember(member.classification_id)}
                disabled={disabled}
                aria-pressed={isSelected}
                aria-label={`${isSelected ? "Deselect" : "Select"} photo ${member.classification_id}`}
                className={`overflow-hidden rounded-md border-2 transition-all ${
                  isSelected ? "border-primary" : "border-transparent opacity-40"
                }`}
              >
                <img
                  src={`/api/crops/${member.crop_id}`}
                  alt=""
                  loading="lazy"
                  decoding="async"
                  className="h-16 w-16 object-cover"
                />
              </button>
            );
          })}
        </div>

        <div className="flex flex-wrap gap-2">
          <Button
            onClick={() => onApprove(selectedIds)}
            disabled={disabled || selectedIds.length === 0}
          >
            Approve {selectedIds.length} as {identity}
          </Button>

          <Button
            variant="outline"
            onClick={() => onReject(selectedIds)}
            disabled={disabled || selectedIds.length === 0}
          >
            Not {identity}
          </Button>

          <Button variant="ghost" onClick={onSplit} disabled={disabled}>
            Multiple {speciesLabel} here? Review individually
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
