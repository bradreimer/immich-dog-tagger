import { IconX } from "@tabler/icons-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface Props {
  notAnimal: boolean;
  onToggle: () => void;
  disabled?: boolean;
}

/**
 * A YOLO false positive, distinct from a species or identity mistake (issue
 * #185) -- this box isn't a dog or cat at all. Mirrors Photo Lookup's
 * DetectionList row, the toggle's original home.
 */
export function NotAnimalToggle({ notAnimal, onToggle, disabled }: Props) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Not a dog or cat?</CardTitle>
      </CardHeader>

      <CardContent>
        <Button type="button" variant="outline" onClick={onToggle} disabled={disabled}>
          {!notAnimal && <IconX className="h-4 w-4" aria-hidden="true" />}
          {notAnimal ? "Undo — this is a dog or cat" : "Not a dog or cat"}
        </Button>
      </CardContent>
    </Card>
  );
}
