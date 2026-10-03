import type { FriendEdge } from "../../../types/metrics";
import { backboneEdges, edgeKey, weightedDegrees } from "./friendsGraph";

/**
 * Deterministic force-directed layout for the Friends in Frame network.
 *
 * The result depends only on the nodes, the (backbone) edges and the canvas
 * size -- never on hover, focus, the connection mode or the slider -- and
 * every random-looking choice is seeded from a pet's id, so positions are the
 * same across re-renders and sessions and a newly added pet only nudges its
 * neighbours. See docs/specs/friends-in-frame.md.
 */

export interface LayoutNode {
  id: number;
  diameter: number;
}

export interface Point {
  x: number;
  y: number;
}

export type Positions = Map<number, Point>;

const GAP = 10;
const LABEL_ROOM = 26;
const ITERATIONS = 300;
const RING_STEP = 0.15;
const OUTER_RING = 0.97;
const MAX_FOCUS_NEIGHBORS = 14;
// Thumbnails carry a name below them, so keep more vertical than horizontal room.
const VERTICAL_WEIGHT = 0.78;
// Relationships outside each pet's strongest few still shape clusters, just gently.
const NON_BACKBONE_PULL = 0.3;

/** Narrow canvases get taller so thumbnails keep their size. */
export function canvasHeight(width: number, nodeCount: number): number {
  if (width < 640) {
    return Math.min(1100, 460 + Math.min(nodeCount, 60) * 14);
  }
  const base = Math.max(420, Math.round(width * 0.42));
  return Math.min(900, base + Math.max(0, nodeCount - 20) * 6);
}

function seeded(seed: number): () => number {
  let a = (seed * 2654435761) >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

interface Box {
  left: number;
  right: number;
  top: number;
  bottom: number;
  cx: number;
  cy: number;
  rx: number;
  ry: number;
}

function boxFor(width: number, height: number, nodes: LayoutNode[]): Box {
  const maxDiameter = nodes.reduce((max, node) => Math.max(max, node.diameter), 0);
  const pad = maxDiameter / 2 + 8;
  const left = pad;
  const right = Math.max(left + 1, width - pad);
  const top = pad;
  const bottom = Math.max(top + 1, height - pad - LABEL_ROOM);
  return {
    left,
    right,
    top,
    bottom,
    cx: (left + right) / 2,
    cy: (top + bottom) / 2,
    rx: (right - left) / 2,
    ry: (bottom - top) / 2,
  };
}

function ellipsePerimeter(a: number, b: number): number {
  return Math.PI * (3 * (a + b) - Math.sqrt((3 * a + b) * (a + 3 * b)));
}

/** Fills concentric rings from the outside in; returns the placements and the innermost ring used. */
function ringPlacement(
  ids: number[],
  diameters: Map<number, number>,
  box: Box,
  outerFactor: number,
): { positions: Positions; innermost: number } {
  const positions: Positions = new Map();
  const queue = [...ids].sort((a, b) => a - b);
  let factor = outerFactor;
  let ring = 0;

  while (queue.length > 0) {
    const a = box.rx * factor;
    const b = box.ry * factor;
    const widest = Math.max(...queue.slice(0, 8).map((id) => diameters.get(id) ?? 48));
    const capacity = Math.max(1, Math.floor(ellipsePerimeter(a, b) / (widest + GAP + 6)));
    const members = queue.splice(0, capacity);
    const offset = -Math.PI / 2 + (ring % 2) * (Math.PI / members.length);

    members.forEach((id, index) => {
      const angle = offset + (2 * Math.PI * index) / members.length;
      positions.set(id, { x: box.cx + a * Math.cos(angle), y: box.cy + b * Math.sin(angle) });
    });

    ring += 1;
    if (queue.length > 0) {
      factor = Math.max(0.3, factor - RING_STEP);
    }
  }

  return { positions, innermost: factor };
}

function clampToBox(point: Point, box: Box): void {
  point.x = Math.min(box.right, Math.max(box.left, point.x));
  point.y = Math.min(box.bottom, Math.max(box.top, point.y));
}

/** Pushes overlapping thumbnails apart. Pinned nodes never move. */
function relax(
  positions: Positions,
  diameters: Map<number, number>,
  pinned: Set<number>,
  box: Box,
  passes = 60,
): void {
  const ids = [...positions.keys()].sort((a, b) => a - b);

  for (let pass = 0; pass < passes; pass++) {
    let moved = false;

    for (let i = 0; i < ids.length; i++) {
      for (let j = i + 1; j < ids.length; j++) {
        const a = positions.get(ids[i])!;
        const b = positions.get(ids[j])!;
        const minDistance = ((diameters.get(ids[i]) ?? 48) + (diameters.get(ids[j]) ?? 48)) / 2 + GAP;
        let dx = b.x - a.x;
        let dy = (b.y - a.y) * VERTICAL_WEIGHT;
        let distance = Math.hypot(dx, dy);

        if (distance >= minDistance) {
          continue;
        }
        if (distance < 0.01) {
          const angle = ((ids[i] * 31 + ids[j]) % 360) * (Math.PI / 180);
          dx = Math.cos(angle);
          dy = Math.sin(angle);
          distance = 1;
        }

        const push = (minDistance - distance) / distance;
        const aPinned = pinned.has(ids[i]);
        const bPinned = pinned.has(ids[j]);
        const aShare = aPinned ? 0 : bPinned ? 1 : 0.5;
        const bShare = bPinned ? 0 : aPinned ? 1 : 0.5;

        a.x -= dx * push * aShare;
        a.y -= (dy * push * aShare) / VERTICAL_WEIGHT;
        b.x += dx * push * bShare;
        b.y += (dy * push * bShare) / VERTICAL_WEIGHT;
        moved = true;
      }
    }

    for (const id of ids) {
      if (!pinned.has(id)) {
        clampToBox(positions.get(id)!, box);
      }
    }
    if (!moved) {
      break;
    }
  }
}

export function computeLayout(input: {
  nodes: LayoutNode[];
  /** Every co-occurrence, not the user-filtered set: the layout must not react to the mode or slider. */
  edges: FriendEdge[];
  width: number;
  height: number;
}): Positions {
  const { edges, width, height } = input;
  const nodes = [...input.nodes].sort((a, b) => a.id - b.id);
  const box = boxFor(width, height, nodes);
  const diameters = new Map(nodes.map((node) => [node.id, node.diameter]));
  const positions: Positions = new Map();

  if (nodes.length === 0) {
    return positions;
  }
  if (nodes.length === 1) {
    positions.set(nodes[0].id, { x: box.cx, y: box.cy });
    return positions;
  }
  if (nodes.length === 2) {
    positions.set(nodes[0].id, { x: box.left + box.rx * 0.5, y: box.cy });
    positions.set(nodes[1].id, { x: box.right - box.rx * 0.5, y: box.cy });
    return positions;
  }

  const degrees = weightedDegrees(edges);
  const backbone = new Set(backboneEdges(edges, nodes.length).map((edge) => edgeKey(edge.a_id, edge.b_id)));
  const connected = nodes.filter((node) => degrees.has(node.id));
  const isolated = nodes.filter((node) => !degrees.has(node.id));

  let regionFactor = 0.92;
  if (isolated.length > 0) {
    const rings = ringPlacement(
      isolated.map((node) => node.id),
      diameters,
      box,
      OUTER_RING,
    );
    rings.positions.forEach((point, id) => positions.set(id, point));
    regionFactor = Math.max(0.4, rings.innermost - 0.3);
  }

  if (connected.length === 1) {
    positions.set(connected[0].id, { x: box.cx, y: box.cy });
  } else if (connected.length > 1) {
    const a = box.rx * regionFactor;
    const b = box.ry * regionFactor;
    const averageDiameter = connected.reduce((sum, node) => sum + node.diameter, 0) / connected.length;
    const ideal = Math.max(averageDiameter + GAP * 2, Math.sqrt((Math.PI * a * b) / connected.length) * 0.6);
    const maxCount = edges.reduce((max, edge) => Math.max(max, edge.count), 1);
    const maxDegree = Math.max(...connected.map((node) => degrees.get(node.id) ?? 0), 1);
    const points = new Map<number, Point>();

    for (const node of connected) {
      const random = seeded(node.id);
      const angle = random() * 2 * Math.PI;
      const radius = Math.sqrt(random()) * 0.7;
      points.set(node.id, {
        x: box.cx + a * radius * Math.cos(angle),
        y: box.cy + b * radius * Math.sin(angle),
      });
    }

    const ids = connected.map((node) => node.id);
    const temperature = Math.min(a, b) * 0.3;

    for (let iteration = 0; iteration < ITERATIONS; iteration++) {
      const cooling = temperature * (1 - iteration / ITERATIONS) + 0.5;
      const force = new Map(ids.map((id) => [id, { x: 0, y: 0 }]));

      for (let i = 0; i < ids.length; i++) {
        for (let j = i + 1; j < ids.length; j++) {
          const p = points.get(ids[i])!;
          const q = points.get(ids[j])!;
          const dx = p.x - q.x;
          const dy = p.y - q.y;
          const distance = Math.max(Math.hypot(dx, dy), 0.01);
          const push = (ideal * ideal) / distance / distance;
          force.get(ids[i])!.x += dx * push;
          force.get(ids[i])!.y += dy * push;
          force.get(ids[j])!.x -= dx * push;
          force.get(ids[j])!.y -= dy * push;
        }
      }

      for (const edge of edges) {
        const p = points.get(edge.a_id);
        const q = points.get(edge.b_id);
        if (!p || !q) {
          continue;
        }
        const dx = q.x - p.x;
        const dy = q.y - p.y;
        const distance = Math.max(Math.hypot(dx, dy), 0.01);
        // Stronger relationships pull harder, so those pets settle closer.
        const strength =
          (0.4 + 1.6 * (edge.count / maxCount)) *
          (backbone.has(edgeKey(edge.a_id, edge.b_id)) ? 1 : NON_BACKBONE_PULL);
        const pull = (distance / ideal) * strength;
        force.get(edge.a_id)!.x += dx * pull;
        force.get(edge.a_id)!.y += dy * pull;
        force.get(edge.b_id)!.x -= dx * pull;
        force.get(edge.b_id)!.y -= dy * pull;
      }

      for (const id of ids) {
        const p = points.get(id)!;
        // Well-connected pets are drawn toward the middle.
        const centrality = 0.25 + 1.25 * ((degrees.get(id) ?? 0) / maxDegree);
        force.get(id)!.x -= ((p.x - box.cx) / a) * ideal * 0.8 * centrality;
        force.get(id)!.y -= ((p.y - box.cy) / b) * ideal * 0.8 * centrality;

        const f = force.get(id)!;
        const magnitude = Math.hypot(f.x, f.y);
        if (magnitude > 0) {
          const step = Math.min(magnitude, cooling) / magnitude;
          p.x += f.x * step;
          p.y += f.y * step;
        }

        const ex = (p.x - box.cx) / a;
        const ey = (p.y - box.cy) / b;
        const reach = Math.hypot(ex, ey);
        if (reach > 1) {
          p.x = box.cx + (ex / reach) * a;
          p.y = box.cy + (ey / reach) * b;
        }
      }
    }

    points.forEach((point, id) => positions.set(id, point));
  }

  relax(positions, diameters, new Set(isolated.map((node) => node.id)), box);
  return positions;
}

/**
 * Click-to-focus arrangement: the focused pet moves to the middle, its
 * strongest friends fan out around it (stronger = closer, in their original
 * angular order so the move reads as continuous), everyone else recedes to
 * the outer rings.
 */
export function focusLayout(input: {
  base: Positions;
  nodes: LayoutNode[];
  focusId: number;
  /** Shared-photo counts for every pet the focused pet appears with. */
  neighborCounts: Map<number, number>;
  width: number;
  height: number;
}): Positions {
  const { base, focusId, neighborCounts, width, height } = input;
  const nodes = [...input.nodes].sort((a, b) => a.id - b.id);
  const box = boxFor(width, height, nodes);
  const diameters = new Map(nodes.map((node) => [node.id, node.diameter]));
  const positions: Positions = new Map();

  positions.set(focusId, { x: box.cx, y: box.cy });

  const friends = [...neighborCounts.entries()]
    .filter(([id]) => id !== focusId && diameters.has(id))
    .sort((a, b) => b[1] - a[1] || a[0] - b[0])
    .slice(0, MAX_FOCUS_NEIGHBORS);
  const strongest = friends.length > 0 ? friends[0][1] : 1;
  const angleOf = (id: number) => {
    const point = base.get(id) ?? { x: box.cx, y: box.cy - 1 };
    return Math.atan2(point.y - box.cy, point.x - box.cx);
  };

  const ordered = friends.map(([id]) => id).sort((a, b) => angleOf(a) - angleOf(b) || a - b);
  const start = ordered.length > 0 ? angleOf(ordered[0]) : 0;
  const hasOthers = nodes.length - 1 > friends.length;
  const maxFactor = hasOthers ? 0.62 : 0.85;

  ordered.forEach((id, index) => {
    const count = neighborCounts.get(id) ?? 0;
    const factor = 0.38 + (maxFactor - 0.38) * (1 - count / strongest);
    const angle = start + (2 * Math.PI * index) / ordered.length;
    positions.set(id, {
      x: box.cx + box.rx * factor * Math.cos(angle),
      y: box.cy + box.ry * factor * Math.sin(angle),
    });
  });

  const others = nodes.map((node) => node.id).filter((id) => id !== focusId && !positions.has(id));
  if (others.length > 0) {
    ringPlacement(others, diameters, box, OUTER_RING).positions.forEach((point, id) =>
      positions.set(id, point),
    );
  }

  relax(positions, diameters, new Set([focusId]), box);
  return positions;
}
