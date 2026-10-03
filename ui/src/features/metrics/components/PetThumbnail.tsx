import { useState } from "react";

import { cn } from "@/lib/utils";
import type { FriendNode } from "../../../types/metrics";

interface Props {
  pet: Pick<FriendNode, "name" | "key_crop_id">;
  /** Diameter in px. */
  size: number;
  className?: string;
}

/**
 * A pet's key thumbnail as a circle. Falls back to the pet's initial when it
 * has no eligible crop or the image can't be loaded, so a pet never looks
 * missing. The name is always rendered next to it, so the image is decorative.
 */
export function PetThumbnail({ pet, size, className }: Props) {
  const [failed, setFailed] = useState(false);
  const showImage = pet.key_crop_id !== null && !failed;

  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center justify-center overflow-hidden rounded-full bg-gradient-to-br from-slate-600 to-slate-800 text-slate-100 ring-2 ring-white/20",
        className,
      )}
      style={{ width: size, height: size, fontSize: Math.round(size * 0.42) }}
      aria-hidden="true"
    >
      {showImage ? (
        <img
          src={`/api/crops/${pet.key_crop_id}`}
          alt=""
          draggable={false}
          loading="lazy"
          className="h-full w-full object-cover"
          onError={() => setFailed(true)}
        />
      ) : (
        <span className="font-semibold">{pet.name.trim().charAt(0).toUpperCase() || "?"}</span>
      )}
    </span>
  );
}
