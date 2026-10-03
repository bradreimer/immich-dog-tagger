import type { FriendEdge, FriendNode } from "../../../types/metrics";

/**
 * Pure data transformation for the Friends in Frame network: which edges to
 * draw, how big a node is, which names to show. No layout and no React --
 * see docs/specs/friends-in-frame.md. Connections always disappear before
 * thumbnails do: nodes are never filtered here.
 */

export type ConnectionMode = "strong" | "top25" | "all";

export const TOP_EDGE_LIMIT = 25;
const WEAK_EDGE_SHARE = 0.08;
const MAX_DEFAULT_LABELS = 12;

export function edgeKey(a: number, b: number): string {
  return a < b ? `${a}:${b}` : `${b}:${a}`;
}

/** Strongest relationships kept per pet in the default view: 3, 2, then 1 as the library grows. */
export function strongNeighborLimit(nodeCount: number): number {
  if (nodeCount <= 8) {
    return 3;
  }
  return nodeCount <= 20 ? 2 : 1;
}

function byStrength(a: FriendEdge, b: FriendEdge): number {
  return b.count - a.count || a.a_id - b.a_id || a.b_id - b.b_id;
}

function topPerNode(edges: FriendEdge[], limit: number): FriendEdge[] {
  const byNode = new Map<number, FriendEdge[]>();
  for (const edge of edges) {
    for (const id of [edge.a_id, edge.b_id]) {
      const list = byNode.get(id) ?? [];
      list.push(edge);
      byNode.set(id, list);
    }
  }

  const kept = new Map<string, FriendEdge>();
  for (const list of byNode.values()) {
    for (const edge of [...list].sort(byStrength).slice(0, limit)) {
      kept.set(edgeKey(edge.a_id, edge.b_id), edge);
    }
  }
  return [...kept.values()].sort(byStrength);
}

/**
 * Each pet's strongest relationships, unfiltered by weakness. This is the
 * skeleton the layout is built from, so it never depends on the user's
 * mode or slider and positions stay put when they change.
 */
export function backboneEdges(edges: FriendEdge[], nodeCount: number): FriendEdge[] {
  return topPerNode(edges, strongNeighborLimit(nodeCount));
}

export function selectEdges(
  edges: FriendEdge[],
  nodeCount: number,
  mode: ConnectionMode,
  minTogether: number,
): FriendEdge[] {
  const eligible = edges.filter((edge) => edge.count >= Math.max(1, minTogether));

  if (mode === "all") {
    return [...eligible].sort(byStrength);
  }
  if (mode === "top25") {
    return [...eligible].sort(byStrength).slice(0, TOP_EDGE_LIMIT);
  }

  const strongest = eligible.reduce((max, edge) => Math.max(max, edge.count), 0);
  const floor = Math.max(1, Math.round(strongest * WEAK_EDGE_SHARE));
  return topPerNode(
    eligible.filter((edge) => edge.count >= floor),
    strongNeighborLimit(nodeCount),
  );
}

export function rankPairs(edges: FriendEdge[], nodes: FriendNode[], limit: number): FriendEdge[] {
  const name = new Map(nodes.map((node) => [node.id, node.name]));
  return [...edges]
    .sort(
      (a, b) =>
        b.count - a.count ||
        (name.get(a.a_id) ?? "").localeCompare(name.get(b.a_id) ?? "") ||
        (name.get(a.b_id) ?? "").localeCompare(name.get(b.b_id) ?? ""),
    )
    .slice(0, limit);
}

/** Total shared photos per pet; how "central" a pet is in the library. */
export function weightedDegrees(edges: FriendEdge[]): Map<number, number> {
  const degrees = new Map<number, number>();
  for (const edge of edges) {
    degrees.set(edge.a_id, (degrees.get(edge.a_id) ?? 0) + edge.count);
    degrees.set(edge.b_id, (degrees.get(edge.b_id) ?? 0) + edge.count);
  }
  return degrees;
}

/**
 * Thumbnail size scales with how many photos the pet is in, but stays within
 * a band that keeps every face recognizable: 48-64px on wide screens, 40-52px
 * on narrow ones, slightly smaller past 30 pets.
 */
export function nodeDiameter(
  imageCount: number,
  maxImageCount: number,
  nodeCount: number,
  compact: boolean,
): number {
  const [min, max] = compact ? [40, 52] : nodeCount > 30 ? [44, 56] : [48, 64];
  const share = maxImageCount > 0 ? Math.sqrt(imageCount / maxImageCount) : 0.5;
  return Math.round(min + (max - min) * share);
}

/**
 * Names shown without interaction: everyone up to 12 pets, then only the
 * most connected 12 (hover or focus reveals the rest).
 */
export function labelledNodeIds(nodes: FriendNode[], edges: FriendEdge[]): Set<number> {
  if (nodes.length <= MAX_DEFAULT_LABELS) {
    return new Set(nodes.map((node) => node.id));
  }
  const degrees = weightedDegrees(edges);
  return new Set(
    [...nodes]
      .sort((a, b) => (degrees.get(b.id) ?? 0) - (degrees.get(a.id) ?? 0) || a.id - b.id)
      .slice(0, MAX_DEFAULT_LABELS)
      .map((node) => node.id),
  );
}
