import { useEffect, useMemo, useRef, useState } from "react";

import { IconArrowLeft, IconExternalLink } from "@tabler/icons-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { FriendEdge, FriendNode } from "../../../types/metrics";
import {
  edgeKey,
  labelledNodeIds,
  nodeDiameter,
  selectEdges,
  type ConnectionMode,
} from "../utils/friendsGraph";
import { canvasHeight, computeLayout, focusLayout } from "../utils/friendsLayout";
import { PetThumbnail } from "./PetThumbnail";

interface Props {
  nodes: FriendNode[];
  edges: FriendEdge[];
  /** Edge to emphasize from outside (hovering a pair card), as `edgeKey`. */
  highlightedEdgeKey?: string | null;
  onNavigate?: (path: string) => void;
}

const FALLBACK_WIDTH = 960;
const WIDTH_STEP = 40;
const COMPACT_BELOW = 560;
const SMALL_LIBRARY_HEIGHT = 300;
const MAX_FOCUS_FRIENDS = 14;
const AT_REST_COUNT_LABELS = 3;

const MODES: { value: ConnectionMode; label: string }[] = [
  { value: "strong", label: "Strong" },
  { value: "top25", label: "Top 25" },
  { value: "all", label: "All" },
];

function pluralImages(count: number): string {
  return `${count} ${count === 1 ? "image" : "images"} together`;
}

function percent(count: number, total: number): number | null {
  return total > 0 ? Math.min(100, Math.round((count / total) * 100)) : null;
}

export function FriendsNetwork({ nodes, edges, highlightedEdgeKey = null, onNavigate }: Props) {
  const stageRef = useRef<HTMLDivElement>(null);
  const [measured, setMeasured] = useState(0);
  const [mode, setMode] = useState<ConnectionMode>("strong");
  const [minTogether, setMinTogether] = useState(1);
  const [hoverId, setHoverId] = useState<number | null>(null);
  const [hoverEdge, setHoverEdge] = useState<{ key: string; x: number; y: number } | null>(null);
  const [focusId, setFocusId] = useState<number | null>(null);

  useEffect(() => {
    const element = stageRef.current;
    if (!element || typeof ResizeObserver === "undefined") {
      return;
    }
    const observer = new ResizeObserver(([entry]) => setMeasured(entry.contentRect.width));
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (focusId === null) {
      return;
    }
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setFocusId(null);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [focusId]);

  // The focused pet may disappear (deactivated, refreshed data).
  const focusNode = focusId !== null ? nodes.find((node) => node.id === focusId) : undefined;
  const focused = focusNode?.id ?? null;

  const count = nodes.length;
  // Quantized so a few pixels of resize never re-runs the layout.
  const width = Math.max(
    WIDTH_STEP * 6,
    Math.floor((measured > 0 ? measured : FALLBACK_WIDTH) / WIDTH_STEP) * WIDTH_STEP,
  );
  const compact = width < COMPACT_BELOW;
  const height = count <= 2 ? SMALL_LIBRARY_HEIGHT : canvasHeight(width, count);

  const maxImages = useMemo(() => nodes.reduce((max, node) => Math.max(max, node.image_count), 0), [nodes]);
  const layoutNodes = useMemo(
    () =>
      nodes.map((node) => ({
        id: node.id,
        diameter: nodeDiameter(node.image_count, maxImages, count, compact),
      })),
    [nodes, maxImages, count, compact],
  );
  const diameterOf = useMemo(() => new Map(layoutNodes.map((node) => [node.id, node.diameter])), [layoutNodes]);
  const nodeById = useMemo(() => new Map(nodes.map((node) => [node.id, node])), [nodes]);

  // Depends only on the data and canvas size: hover, focus, mode and the
  // slider never move anything, so the network stays calm.
  const basePositions = useMemo(
    () => computeLayout({ nodes: layoutNodes, edges, width, height }),
    [layoutNodes, edges, width, height],
  );

  const maxEdgeCount = useMemo(() => edges.reduce((max, edge) => Math.max(max, edge.count), 0), [edges]);
  const eligibleEdges = useMemo(
    () => edges.filter((edge) => edge.count >= Math.max(1, minTogether)),
    [edges, minTogether],
  );

  const focusEdges = useMemo(() => {
    if (focused === null) {
      return [];
    }
    return eligibleEdges
      .filter((edge) => edge.a_id === focused || edge.b_id === focused)
      .sort((a, b) => b.count - a.count || a.a_id - b.a_id || a.b_id - b.b_id)
      .slice(0, MAX_FOCUS_FRIENDS);
  }, [eligibleEdges, focused]);

  const positions = useMemo(() => {
    if (focused === null) {
      return basePositions;
    }
    return focusLayout({
      base: basePositions,
      nodes: layoutNodes,
      focusId: focused,
      neighborCounts: new Map(
        focusEdges.map((edge) => [edge.a_id === focused ? edge.b_id : edge.a_id, edge.count]),
      ),
      width,
      height,
    });
  }, [basePositions, focused, focusEdges, layoutNodes, width, height]);

  const visibleEdges = useMemo(
    () => (focused !== null ? focusEdges : selectEdges(edges, count, mode, minTogether)),
    [focused, focusEdges, edges, count, mode, minTogether],
  );
  const totalSelectable = useMemo(
    () => selectEdges(edges, count, "all", minTogether).length,
    [edges, count, minTogether],
  );

  const labelled = useMemo(() => labelledNodeIds(nodes, edges), [nodes, edges]);
  const visibleDegree = useMemo(() => {
    const degree = new Map<number, number>();
    for (const edge of visibleEdges) {
      degree.set(edge.a_id, (degree.get(edge.a_id) ?? 0) + 1);
      degree.set(edge.b_id, (degree.get(edge.b_id) ?? 0) + 1);
    }
    return degree;
  }, [visibleEdges]);
  const connectedAnywhere = useMemo(() => {
    const ids = new Set<number>();
    for (const edge of edges) {
      ids.add(edge.a_id);
      ids.add(edge.b_id);
    }
    return ids;
  }, [edges]);

  const activeId = hoverId ?? focused;
  const activeEdge = hoverEdge?.key ?? highlightedEdgeKey;
  const hasSelection = activeId !== null || activeEdge !== null;

  const litNodes = useMemo(() => {
    const lit = new Set<number>();
    if (activeId !== null) {
      lit.add(activeId);
      for (const edge of visibleEdges) {
        if (edge.a_id === activeId) {
          lit.add(edge.b_id);
        } else if (edge.b_id === activeId) {
          lit.add(edge.a_id);
        }
      }
    }
    if (activeEdge !== null) {
      for (const edge of visibleEdges) {
        if (edgeKey(edge.a_id, edge.b_id) === activeEdge) {
          lit.add(edge.a_id);
          lit.add(edge.b_id);
        }
      }
    }
    return lit;
  }, [activeId, activeEdge, visibleEdges]);

  const restingCountKeys = useMemo(
    () => new Set(visibleEdges.slice(0, AT_REST_COUNT_LABELS).map((edge) => edgeKey(edge.a_id, edge.b_id))),
    [visibleEdges],
  );

  const maxVisible = visibleEdges.reduce((max, edge) => Math.max(max, edge.count), 1);
  const interactive = count >= 3;
  const tooltipEdge = hoverEdge ? edges.find((edge) => edgeKey(edge.a_id, edge.b_id) === hoverEdge.key) : undefined;

  const showControls = count >= 3 && edges.length > 0;

  return (
    <div className="space-y-3">
      {focusNode ? (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border bg-muted/40 px-3 py-2">
          <div className="flex min-w-0 items-center gap-3">
            <PetThumbnail pet={focusNode} size={36} />
            <p className="truncate text-sm">
              Focused on <span className="font-semibold">{focusNode.name}</span>
              <span className="text-muted-foreground">
                {focusEdges.length > 0
                  ? ` · ${focusEdges.length} ${focusEdges.length === 1 ? "friend" : "friends"} in frame`
                  : " · no shared appearances at this setting"}
              </span>
            </p>
          </div>
          <div className="flex items-center gap-2">
            {onNavigate && (
              <Button variant="outline" size="sm" onClick={() => onNavigate(`/dogs/${focusNode.id}/insights`)}>
                <IconExternalLink className="h-4 w-4" aria-hidden="true" />
                Insights
              </Button>
            )}
            <Button size="sm" onClick={() => setFocusId(null)}>
              <IconArrowLeft className="h-4 w-4" aria-hidden="true" />
              Back to all friends
            </Button>
          </div>
        </div>
      ) : (
        showControls && (
          <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2">
            <div className="flex items-center gap-2 text-sm">
              <span className="text-muted-foreground">Connections</span>
              <div className="inline-flex rounded-lg border p-0.5" role="group" aria-label="Connections to show">
                {MODES.map((option) => (
                  <button
                    key={option.value}
                    type="button"
                    aria-pressed={mode === option.value}
                    onClick={() => setMode(option.value)}
                    className={cn(
                      "rounded-md px-2.5 py-1 text-xs font-medium transition-colors",
                      mode === option.value
                        ? "bg-primary text-primary-foreground"
                        : "text-muted-foreground hover:text-foreground",
                    )}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            </div>

            {maxEdgeCount >= 3 && (
              <label className="flex items-center gap-2 text-sm text-muted-foreground">
                <span>
                  Together in at least <span className="font-medium text-foreground">{minTogether}</span>
                </span>
                <input
                  type="range"
                  min={1}
                  max={maxEdgeCount}
                  value={Math.min(minTogether, maxEdgeCount)}
                  onChange={(event) => setMinTogether(Number(event.target.value))}
                  aria-label="Minimum images together"
                  className="h-1 w-28 cursor-pointer accent-primary"
                />
              </label>
            )}
          </div>
        )
      )}

      <div
        ref={stageRef}
        className="relative mx-auto w-full overflow-hidden rounded-xl border border-white/10 bg-[radial-gradient(ellipse_at_center,#1c2b4d_0%,#0d1526_55%,#080d18_100%)] shadow-inner"
        style={{ height }}
        data-testid="friends-stage"
      >
        <svg className="absolute inset-0 h-full w-full" width={width} height={height} aria-hidden="true">
          <g key={focused ?? "all"} className="animate-in fade-in duration-500">
            {visibleEdges.map((edge) => {
              const a = positions.get(edge.a_id);
              const b = positions.get(edge.b_id);
              if (!a || !b) {
                return null;
              }
              const key = edgeKey(edge.a_id, edge.b_id);
              const strength = edge.count / maxVisible;
              const touches = activeId !== null && (edge.a_id === activeId || edge.b_id === activeId);
              const picked = activeEdge === key;
              const lit = touches || picked;
              const dimmed = hasSelection && !lit;

              return (
                <g key={key}>
                  <line
                    x1={a.x}
                    y1={a.y}
                    x2={b.x}
                    y2={b.y}
                    stroke={lit ? "#a9ccff" : "#6aa8ff"}
                    strokeLinecap="round"
                    strokeWidth={1.2 + 5.8 * Math.pow(strength, 0.6) + (lit ? 0.8 : 0)}
                    strokeOpacity={dimmed ? 0.07 : lit ? 0.95 : 0.22 + 0.5 * strength}
                    style={{ transition: "stroke-opacity 200ms" }}
                  />
                  <line
                    x1={a.x}
                    y1={a.y}
                    x2={b.x}
                    y2={b.y}
                    stroke="transparent"
                    strokeWidth={14}
                    pointerEvents="stroke"
                    className="cursor-pointer"
                    data-testid={`edge-${key}`}
                    onMouseMove={(event) => {
                      const rect = stageRef.current?.getBoundingClientRect();
                      setHoverEdge({
                        key,
                        x: event.clientX - (rect?.left ?? 0),
                        y: event.clientY - (rect?.top ?? 0),
                      });
                    }}
                    onMouseLeave={() => setHoverEdge(null)}
                  />
                </g>
              );
            })}
          </g>
        </svg>

        {visibleEdges.map((edge) => {
          const key = edgeKey(edge.a_id, edge.b_id);
          const touches = activeId !== null && (edge.a_id === activeId || edge.b_id === activeId);
          const showCount =
            touches || activeEdge === key || (!hasSelection && restingCountKeys.has(key));
          const a = positions.get(edge.a_id);
          const b = positions.get(edge.b_id);
          if (!showCount || !a || !b) {
            return null;
          }
          // On a short edge the pill would sit under the thumbnails.
          const clearance = ((diameterOf.get(edge.a_id) ?? 48) + (diameterOf.get(edge.b_id) ?? 48)) / 2 + 22;
          if (Math.hypot(a.x - b.x, a.y - b.y) < clearance) {
            return null;
          }
          return (
            <span
              key={`count-${key}`}
              className="pointer-events-none absolute -translate-x-1/2 -translate-y-1/2 rounded-full border border-white/15 bg-slate-950/85 px-1.5 py-0.5 text-[11px] font-medium tabular-nums text-slate-100"
              style={{ left: (a.x + b.x) / 2, top: (a.y + b.y) / 2 }}
            >
              {edge.count}
            </span>
          );
        })}

        {nodes.map((pet) => {
          const point = positions.get(pet.id);
          const diameter = diameterOf.get(pet.id) ?? 48;
          if (!point) {
            return null;
          }
          const isActive = activeId === pet.id || (activeEdge !== null && litNodes.has(pet.id));
          const dimmed = hasSelection && !litNodes.has(pet.id);
          const showName = labelled.has(pet.id) || litNodes.has(pet.id) || hoverId === pet.id;
          const quiet = !(focused !== null) && count >= 2 && edges.length > 0 && !visibleDegree.has(pet.id);
          const caption = quiet
            ? connectedAnywhere.has(pet.id)
              ? "No strong connections"
              : "No shared photos"
            : null;

          return (
            <button
              key={pet.id}
              type="button"
              aria-label={`${pet.name}, ${pet.image_count} ${pet.image_count === 1 ? "photo" : "photos"}`}
              className={cn(
                "group absolute left-0 top-0 rounded-full outline-none transition-[transform,opacity] duration-500 ease-out focus-visible:ring-2 focus-visible:ring-sky-300 motion-reduce:transition-none",
                interactive ? "cursor-pointer" : "cursor-default",
                dimmed ? "opacity-30" : "opacity-100",
                isActive ? "z-20" : "z-10",
              )}
              style={{
                width: diameter,
                height: diameter,
                transform: `translate(${point.x - diameter / 2}px, ${point.y - diameter / 2}px)`,
              }}
              onMouseEnter={() => setHoverId(pet.id)}
              onMouseLeave={() => setHoverId(null)}
              onFocus={() => setHoverId(pet.id)}
              onBlur={() => setHoverId(null)}
              onClick={() => {
                if (interactive) {
                  setHoverId(null);
                  setFocusId(focused === pet.id ? null : pet.id);
                }
              }}
            >
              <PetThumbnail
                pet={pet}
                size={diameter}
                className={cn(
                  "transition-[transform,box-shadow] duration-200",
                  isActive
                    ? "scale-[1.12] shadow-[0_0_26px_rgba(106,168,255,0.6)] ring-sky-200/70"
                    : caption
                      ? "opacity-80"
                      : "",
                )}
              />
              <span
                className={cn(
                  "pointer-events-none absolute left-1/2 top-full mt-1 w-28 -translate-x-1/2 text-center transition-opacity duration-200",
                  showName ? "opacity-100" : "opacity-0",
                )}
              >
                <span className="block truncate text-xs font-medium leading-4 text-slate-100 [text-shadow:0_1px_3px_rgba(0,0,0,0.8)]">
                  {pet.name}
                </span>
                {caption && ((count <= 12 && !compact) || hoverId === pet.id) && (
                  <span className="block truncate text-[10px] leading-3 text-slate-400">{caption}</span>
                )}
              </span>
            </button>
          );
        })}

        {tooltipEdge && hoverEdge && (
          <div
            role="tooltip"
            className="pointer-events-none absolute z-30 -translate-x-1/2 -translate-y-[130%] whitespace-nowrap rounded-lg border border-white/15 bg-slate-950/95 px-3 py-2 text-xs text-slate-100 shadow-lg"
            style={{ left: hoverEdge.x, top: hoverEdge.y }}
          >
            {(() => {
              const a = nodeById.get(tooltipEdge.a_id);
              const b = nodeById.get(tooltipEdge.b_id);
              if (!a || !b) {
                return null;
              }
              const shareA = percent(tooltipEdge.count, a.image_count);
              const shareB = percent(tooltipEdge.count, b.image_count);
              return (
                <>
                  <p className="text-sm font-semibold">
                    {a.name} + {b.name}
                  </p>
                  <p>{pluralImages(tooltipEdge.count)}</p>
                  {shareA !== null && shareB !== null && (
                    <p className="mt-1 text-slate-400">
                      {shareA}% of {a.name}&apos;s photos · {shareB}% of {b.name}&apos;s
                    </p>
                  )}
                </>
              );
            })()}
          </div>
        )}
      </div>

      {count === 1 && <p className="text-center text-sm text-muted-foreground">No relationships yet</p>}
      {count >= 2 && edges.length === 0 && (
        <p className="text-center text-sm text-muted-foreground">
          No shared appearances yet. Pets connect here once they are confirmed in the same photo.
        </p>
      )}

      {focused === null && showControls && (
        <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
          <span>
            Showing {visibleEdges.length} of {totalSelectable} connections
            {minTogether > 1 ? ` (together in ${minTogether}+ images)` : ""}
          </span>
          {mode !== "all" && visibleEdges.length < totalSelectable ? (
            <Button variant="ghost" size="sm" onClick={() => setMode("all")}>
              Show more connections
            </Button>
          ) : (
            mode === "all" &&
            totalSelectable > 0 && (
              <Button variant="ghost" size="sm" onClick={() => setMode("strong")}>
                Show fewer connections
              </Button>
            )
          )}
        </div>
      )}
    </div>
  );
}
