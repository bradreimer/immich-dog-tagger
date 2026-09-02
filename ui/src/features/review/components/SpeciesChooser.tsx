import { IconCat, IconDog } from "@tabler/icons-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

import { SPECIES_STYLES } from "../utils/speciesStyles";

interface Props {
  species: string;
  onCorrectSpecies: (species: "dog" | "cat") => void;
  disabled?: boolean;
}

/**
 * Content-only (no Card wrapper) so ReviewCard can group this with
 * NotAnimalToggle inside one shared card -- see
 * docs/specs/review-panel-space-efficiency.md.
 */
export function SpeciesChooser({ species, onCorrectSpecies, disabled }: Props) {
  return (
    <div className="space-y-2">
      <div className="text-sm font-medium">Wrong species?</div>

      <div
        className="flex flex-wrap gap-2"
        role="group"
        aria-label="Correct species"
      >
        <Button
          variant="outline"
          className={cn(SPECIES_STYLES.dog)}
          aria-pressed={species === "dog"}
          disabled={disabled || species === "dog"}
          onClick={() => onCorrectSpecies("dog")}
        >
          <IconDog className="h-4 w-4" aria-hidden="true" />
          {species === "dog" ? "Dog (current)" : "Dog"}
        </Button>

        <Button
          variant="outline"
          className={cn(SPECIES_STYLES.cat)}
          aria-pressed={species === "cat"}
          disabled={disabled || species === "cat"}
          onClick={() => onCorrectSpecies("cat")}
        >
          <IconCat className="h-4 w-4" aria-hidden="true" />
          {species === "cat" ? "Cat (current)" : "Cat"}
        </Button>
      </div>
    </div>
  );
}
