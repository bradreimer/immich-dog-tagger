import { useState } from "react";

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

/**
 * Renders the full photo at natural aspect ratio (no letterboxing) with one
 * absolutely-positioned box per detection, sized as a percentage of the
 * image's natural dimensions so boxes stay aligned with the pixels
 * `Detection.x1/y1/x2/y2` describe regardless of how large the image is
 * rendered on screen.
 */
export function PhotoLookupImage({ imageUrl, detections }: Props) {
  const [naturalSize, setNaturalSize] = useState<NaturalSize | null>(null);

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

        {naturalSize &&
          detections.map((detection, index) => {
            const identified = Boolean(detection.identity);

            return (
              <div
                key={detection.detection_id}
                className={cn(
                  "absolute border-2 shadow-[0_0_0_1px_rgba(0,0,0,0.3)]",
                  identified ? "border-status-good" : "border-status-warning",
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
                    identified ? "bg-status-good" : "bg-status-warning",
                  )}
                >
                  {index + 1}. {detection.identity ?? "Unknown"}
                </span>
              </div>
            );
          })}
      </div>
    </Card>
  );
}
