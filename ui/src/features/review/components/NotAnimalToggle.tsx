import { IconX } from "@tabler/icons-react";
import { Button } from "@/components/ui/button";

interface Props {
  notAnimal: boolean;
  onToggle: () => void;
  disabled?: boolean;
}

/**
 * A YOLO false positive, distinct from a species or identity mistake (issue
 * #185) -- this box isn't a dog or cat at all. Mirrors Photo Lookup's
 * DetectionList row, the toggle's original home.
 *
 * Content-only (no Card wrapper) so ReviewCard can group this with
 * SpeciesChooser inside one shared card -- see
 * docs/specs/review-panel-space-efficiency.md.
 */
export function NotAnimalToggle({ notAnimal, onToggle, disabled }: Props) {
  return (
    <div className="space-y-2">
      <div className="text-sm font-medium">Not a dog or cat?</div>

      <Button type="button" variant="outline" onClick={onToggle} disabled={disabled}>
        {!notAnimal && <IconX className="h-4 w-4" aria-hidden="true" />}
        {notAnimal ? "Undo — this is a dog or cat" : "Not a dog or cat"}
      </Button>
    </div>
  );
}
