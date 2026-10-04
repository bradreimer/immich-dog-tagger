import { useMemo, useState } from "react";

import { IconArrowsLeftRight } from "@tabler/icons-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { FriendEdge, FriendNode } from "../../../types/metrics";
import { edgeKey, rankPairs } from "../utils/friendsGraph";
import { PetThumbnail } from "./PetThumbnail";

export const INITIAL_PAIR_COUNT = 6;
export const MAX_PAIR_COUNT = 24;

interface Props {
  nodes: FriendNode[];
  edges: FriendEdge[];
  onHoverPair?: (key: string | null) => void;
  /** Opens the Library scoped to photos containing both pets. */
  onNavigate?: (path: string) => void;
}

export function MostCommonPairs({ nodes, edges, onHoverPair, onNavigate }: Props) {
  const [expanded, setExpanded] = useState(false);
  const nodeById = useMemo(() => new Map(nodes.map((node) => [node.id, node])), [nodes]);
  const ranked = useMemo(() => rankPairs(edges, nodes, MAX_PAIR_COUNT), [edges, nodes]);
  const shown = expanded ? ranked : ranked.slice(0, INITIAL_PAIR_COUNT);
  const hasMore = edges.length > INITIAL_PAIR_COUNT;

  if (ranked.length === 0) {
    return null;
  }

  return (
    <section className="space-y-3" aria-labelledby="most-common-pairs-heading">
      <div className="flex items-center justify-between gap-3">
        <h3 id="most-common-pairs-heading" className="text-sm font-semibold tracking-tight">
          Most Common Pairs
        </h3>
        {hasMore && (
          <Button variant="ghost" size="sm" onClick={() => setExpanded((value) => !value)}>
            {expanded ? "Show fewer" : `Show more (${Math.min(edges.length, MAX_PAIR_COUNT)})`}
          </Button>
        )}
      </div>

      <ul
        className={cn(
          "gap-3",
          expanded
            ? "grid grid-cols-[repeat(auto-fill,minmax(14rem,1fr))]"
            : "-mx-1 flex snap-x snap-mandatory overflow-x-auto px-1 pb-2",
        )}
      >
        {shown.map((edge) => {
          const a = nodeById.get(edge.a_id);
          const b = nodeById.get(edge.b_id);
          if (!a || !b) {
            return null;
          }
          const key = edgeKey(edge.a_id, edge.b_id);
          const openPair = () => {
            const params = new URLSearchParams();
            params.append("identity", a.name);
            params.append("identity", b.name);
            onNavigate?.(`/library?${params.toString()}`);
          };

          return (
            <li
              key={key}
              tabIndex={0}
              role={onNavigate ? "link" : undefined}
              aria-label={onNavigate ? `View photos of ${a.name} and ${b.name} together` : undefined}
              onClick={openPair}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  openPair();
                }
              }}
              className={cn(
                "snap-start rounded-xl border bg-muted/30 p-3 outline-none focus-visible:ring-2 focus-visible:ring-ring",
                onNavigate && "cursor-pointer",
                expanded ? "" : "w-56 shrink-0",
              )}
              onMouseEnter={() => onHoverPair?.(key)}
              onMouseLeave={() => onHoverPair?.(null)}
              onFocus={() => onHoverPair?.(key)}
              onBlur={() => onHoverPair?.(null)}
            >
              <div className="flex items-center justify-center gap-3">
                <PetThumbnail pet={a} size={52} />
                <IconArrowsLeftRight className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
                <PetThumbnail pet={b} size={52} />
              </div>
              <p className="mt-2 truncate text-center text-sm font-medium">
                {a.name} + {b.name}
              </p>
              <p className="text-center text-xs text-muted-foreground">
                {edge.count} {edge.count === 1 ? "image" : "images"} together
              </p>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
