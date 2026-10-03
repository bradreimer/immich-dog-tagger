import { describe, expect, it } from "vitest";

import type { FriendEdge } from "../../../types/metrics";
import { canvasHeight, computeLayout, focusLayout, type LayoutNode, type Positions } from "./friendsLayout";

const WIDTH = 960;

function makeNodes(n: number, diameter = 56): LayoutNode[] {
  return Array.from({ length: n }, (_, i) => ({ id: i + 1, diameter }));
}

// Pets 1..k form a tight clique; the rest chain loosely or stay isolated.
function clusterEdges(n: number, isolatedFrom: number): FriendEdge[] {
  const edges: FriendEdge[] = [];
  for (let a = 1; a < isolatedFrom; a++) {
    for (let b = a + 1; b < isolatedFrom; b++) {
      edges.push({ a_id: a, b_id: b, count: a <= 4 && b <= 4 ? 40 : 2 });
    }
  }
  return edges.length > 0 || n === 0 ? edges : [];
}

function layoutFor(n: number, isolatedFrom = n + 1, width = WIDTH) {
  const nodes = makeNodes(n);
  const edges = clusterEdges(n, isolatedFrom);
  const height = canvasHeight(width, n);
  return { nodes, edges, height, positions: computeLayout({ nodes, edges, width, height }) };
}

function minGap(positions: Positions, nodes: LayoutNode[]): number {
  let min = Infinity;
  for (let i = 0; i < nodes.length; i++) {
    for (let j = i + 1; j < nodes.length; j++) {
      const p = positions.get(nodes[i].id)!;
      const q = positions.get(nodes[j].id)!;
      const gap = Math.hypot(p.x - q.x, p.y - q.y) - (nodes[i].diameter + nodes[j].diameter) / 2;
      min = Math.min(min, gap);
    }
  }
  return min;
}

describe("computeLayout", () => {
  it("is deterministic for the same input", () => {
    const first = layoutFor(20, 17);
    const second = layoutFor(20, 17);

    expect([...second.positions.entries()]).toEqual([...first.positions.entries()]);
  });

  it("places a lone pet in the middle", () => {
    const { positions, height } = layoutFor(1);
    const point = positions.get(1)!;

    expect(point.x).toBeCloseTo(WIDTH / 2, 0);
    expect(point.y).toBeGreaterThan(0);
    expect(point.y).toBeLessThan(height);
  });

  it("places two pets side by side on one row", () => {
    const { positions } = layoutFor(2, 3);

    expect(positions.get(1)!.y).toBeCloseTo(positions.get(2)!.y, 5);
    expect(positions.get(1)!.x).toBeLessThan(positions.get(2)!.x);
  });

  it("returns every pet inside the canvas at 1, 2, 5, 10, 20 and 50 pets", () => {
    for (const n of [1, 2, 5, 10, 20, 50]) {
      const { positions, nodes, height } = layoutFor(n, Math.max(2, n - 3));

      expect(positions.size).toBe(n);
      for (const node of nodes) {
        const point = positions.get(node.id)!;
        expect(point.x).toBeGreaterThanOrEqual(node.diameter / 2 - 1);
        expect(point.x).toBeLessThanOrEqual(WIDTH);
        expect(point.y).toBeGreaterThanOrEqual(node.diameter / 2 - 1);
        expect(point.y).toBeLessThanOrEqual(height);
      }
    }
  });

  it("never overlaps thumbnails, even with 50 pets", () => {
    for (const n of [5, 20, 50]) {
      const { positions, nodes } = layoutFor(n, Math.max(2, n - 6));

      expect(minGap(positions, nodes)).toBeGreaterThan(-1);
    }
  });

  it("keeps pets without co-occurrences toward the perimeter and hubs toward the middle", () => {
    const { positions, height } = layoutFor(14, 9);
    const cx = WIDTH / 2;
    const cy = (height - 26) / 2;
    const distance = (id: number) => {
      const p = positions.get(id)!;
      return Math.hypot((p.x - cx) / (WIDTH / 2), (p.y - cy) / (height / 2));
    };
    const isolated = [9, 10, 11, 12, 13, 14].map(distance);
    const hubs = [1, 2, 3, 4].map(distance);

    expect(Math.min(...isolated)).toBeGreaterThan(Math.max(...hubs));
  });

  it("pulls strongly connected pets closer than weakly connected ones", () => {
    const nodes = makeNodes(6);
    const edges: FriendEdge[] = [
      { a_id: 1, b_id: 2, count: 50 },
      { a_id: 1, b_id: 3, count: 1 },
      { a_id: 3, b_id: 4, count: 20 },
      { a_id: 4, b_id: 5, count: 20 },
      { a_id: 5, b_id: 6, count: 20 },
    ];
    const positions = computeLayout({ nodes, edges, width: WIDTH, height: canvasHeight(WIDTH, 6) });
    const d = (a: number, b: number) =>
      Math.hypot(
        positions.get(a)!.x - positions.get(b)!.x,
        positions.get(a)!.y - positions.get(b)!.y,
      );

    expect(d(1, 2)).toBeLessThan(d(1, 3));
  });
});

describe("canvasHeight", () => {
  it("is taller on narrow screens and grows with the library", () => {
    expect(canvasHeight(360, 10)).toBeGreaterThan(canvasHeight(960, 10));
    expect(canvasHeight(960, 50)).toBeGreaterThan(canvasHeight(960, 10));
    expect(canvasHeight(960, 500)).toBeLessThanOrEqual(900);
  });
});

describe("focusLayout", () => {
  it("centers the focused pet and keeps stronger friends nearer than weaker ones", () => {
    const { nodes, positions, height } = layoutFor(12, 12);
    const focus = focusLayout({
      base: positions,
      nodes,
      focusId: 1,
      neighborCounts: new Map([
        [2, 40],
        [3, 20],
        [4, 5],
      ]),
      width: WIDTH,
      height,
    });
    const center = focus.get(1)!;
    const d = (id: number) => Math.hypot(focus.get(id)!.x - center.x, focus.get(id)!.y - center.y);

    expect(center.x).toBeCloseTo(WIDTH / 2, 0);
    expect(d(2)).toBeLessThan(d(4));
    expect(minGap(focus, nodes)).toBeGreaterThan(-1);
    expect(focus.size).toBe(12);
  });

  it("is deterministic", () => {
    const { nodes, positions, height } = layoutFor(8, 8);
    const args = {
      base: positions,
      nodes,
      focusId: 2,
      neighborCounts: new Map([[1, 3]]),
      width: WIDTH,
      height,
    };

    expect([...focusLayout(args).entries()]).toEqual([...focusLayout(args).entries()]);
  });
});
