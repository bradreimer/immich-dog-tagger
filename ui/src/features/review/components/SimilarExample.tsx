import { useState } from "react";

import { IconChevronDown } from "@tabler/icons-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { cn } from "@/lib/utils";

interface Props {
  exampleId: number;
  identity: string;
  similarity: number;
  capturedAt: string | null;
}

/**
 * Collapsed by default: the reference image is only mounted (and therefore
 * only fetched) once a reviewer actually expands this section, so flipping
 * through a queue doesn't pay for an image nobody looks at (issue #208).
 * Stays mounted after the first expand so re-collapsing doesn't refetch it.
 */
export function SimilarExample({
  exampleId,
  identity,
  similarity,
  capturedAt,
}: Props) {
  const [open, setOpen] = useState(false);
  const [hasOpened, setHasOpened] = useState(false);

  return (
    <Card>
      <Collapsible
        open={open}
        onOpenChange={(next) => {
          setOpen(next);
          if (next) {
            setHasOpened(true);
          }
        }}
      >
        <CardHeader>
          <CollapsibleTrigger>
            <span className="flex flex-1 items-center gap-2">
              <CardTitle>Similar memory</CardTitle>

              <span className="text-sm font-normal text-muted-foreground">
                {identity}
              </span>

              <Badge variant="secondary">
                {(similarity * 100).toFixed(1)}%
              </Badge>
            </span>

            <IconChevronDown
              className={cn(
                "h-4 w-4 shrink-0 text-muted-foreground transition-transform",
                open && "rotate-180",
              )}
              aria-hidden="true"
            />
          </CollapsibleTrigger>
        </CardHeader>

        <CollapsibleContent keepMounted={hasOpened}>
          <CardContent className="space-y-3 pt-0">
            {hasOpened && (
              <img
                src={`/api/embedding-examples/${exampleId}/image`}
                alt={`Similar example of ${identity}`}
                className="w-full rounded-lg object-contain"
              />
            )}

            {capturedAt && (
              <div className="text-sm text-muted-foreground">
                Captured{" "}
                {new Date(capturedAt).toLocaleDateString()}
              </div>
            )}
          </CardContent>
        </CollapsibleContent>
      </Collapsible>
    </Card>
  );
}
