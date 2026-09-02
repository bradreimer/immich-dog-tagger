import { useState } from "react";

import { IconAlertTriangle } from "@tabler/icons-react";

import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { PhotoLookupDetection } from "@/types/photoLookup";

interface Props {
  imageUrl: string;
  detections: PhotoLookupDetection[];
}

interface NaturalSize {
  width: number;
  height: number;
}

// A detection whose box falls outside the displayed image's own dimensions
// cannot be positioned meaningfully -- most commonly this means the
// detection predates an EXIF-orientation fix (issues #137/#192) and was
// computed against a differently-rotated decode of this photo than the one
// served today (issue #220). Rendering it anyway would place a box off-frame
// or over the wrong subject, which reads as a fresh bug rather than known
// stale data, so it's flagged instead of drawn.
function isOutOfBounds(detection: PhotoLookupDetection, size: NaturalSize): boolean {
  return (
    detection.x1 < 0 ||
    detection.y1 < 0 ||
    detection.x2 <= detection.x1 ||
    detection.y2 <= detection.y1 ||
    detection.x2 > size.width ||
    detection.y2 > size.height
  );
}

function describeStaleDetections(indexes: number[]): string {
  const numbers = indexes.map((index) => index + 1).join(", ");

  return indexes.length > 1
    ? `Boxes not shown for detections ${numbers}: coordinates fall outside this image, which usually means they predate an orientation fix and need reprocessing.`
    : `Box not shown for detection ${numbers}: coordinates fall outside this image, which usually means it predates an orientation fix and needs reprocessing.`;
}

/**
 * Renders the full photo at natural aspect ratio (no letterboxing) with one
 * absolutely-positioned box per detection, sized as a percentage of the
 * image's natural dimensions so boxes stay aligned with the pixels
 * `Detection.x1/y1/x2/y2` describe regardless of how large the image is
 * rendered on screen.
 */
export function PhotoLookupImage({ imageUrl, detections }: Props) {
  const [naturalSize, setNaturalSize] = useState<NaturalSize | null>(null);

  const staleIndexes = naturalSize
    ? detections
        .map((detection, index) => (isOutOfBounds(detection, naturalSize) ? index : null))
        .filter((index): index is number => index !== null)
    : [];

  return (
    <Card className="overflow-hidden p-0">
      <div className="relative w-full">
        <img
          src={imageUrl}
          alt="Photo looked up from Immich"
          className="block w-full"
          onLoad={(event) => {
            const img = event.currentTarget;
            setNaturalSize({
              width: img.naturalWidth,
              height: img.naturalHeight,
            });
          }}
        />

        {staleIndexes.length > 0 && (
          <div className="absolute inset-x-0 top-0 z-10 flex items-start gap-2 bg-status-warning px-3 py-2 text-xs font-medium text-white">
            <IconAlertTriangle className="h-4 w-4 shrink-0" aria-hidden="true" />
            <span>{describeStaleDetections(staleIndexes)}</span>
          </div>
        )}

        {naturalSize &&
          detections.map((detection, index) => {
            if (isOutOfBounds(detection, naturalSize)) {
              return null;
            }

            const identified = Boolean(detection.identity);

            return (
              <div
                key={detection.detection_id}
                className={cn(
                  "absolute shadow-[0_0_0_1px_rgba(0,0,0,0.3)]",
                  detection.not_animal
                    ? "border-2 border-dashed border-muted-foreground/60 opacity-60"
                    : cn(
                        "border-2",
                        identified ? "border-status-good" : "border-status-warning",
                      ),
                )}
                style={{
                  left: `${(detection.x1 / naturalSize.width) * 100}%`,
                  top: `${(detection.y1 / naturalSize.height) * 100}%`,
                  width: `${((detection.x2 - detection.x1) / naturalSize.width) * 100}%`,
                  height: `${((detection.y2 - detection.y1) / naturalSize.height) * 100}%`,
                }}
              >
                <span
                  className={cn(
                    "absolute left-0 top-0 whitespace-nowrap rounded-br px-1.5 py-0.5 text-xs font-semibold text-white",
                    detection.not_animal
                      ? "bg-muted-foreground/80"
                      : identified
                        ? "bg-status-good"
                        : "bg-status-warning",
                  )}
                >
                  {index + 1}. {detection.not_animal ? "Not a dog or cat" : (detection.identity ?? "Unknown")}
                </span>
              </div>
            );
          })}
      </div>
    </Card>
  );
}
