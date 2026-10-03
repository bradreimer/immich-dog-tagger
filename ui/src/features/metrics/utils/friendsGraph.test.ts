import { describe, expect, it } from "vitest";

import type { FriendEdge, FriendNode } from "../../../types/metrics";
import {
  TOP_EDGE_LIMIT,
  backboneEdges,
  edgeKey,
  labelledNodeIds,
  nodeDiameter,
  rankPairs,
  selectEdges,
  strongNeighborLimit,
} from "./friendsGraph";

function node(id: number, name = `Pet ${id}`, imageCount = 10): FriendNode {
  return { id, name, species: "dog", image_count: imageCount, key_crop_id: null };
}

function edge(a: number, b: number, count: number): FriendEdge {
  return { a_id: a, b_id: b, count };
}

// A dense library: every pet shares photos with every other pet.
function completeEdges(n: number): FriendEdge[] {
  const edges: FriendEdge[] = [];
  for (let a = 1; a <= n; a++) {
    for (let b = a + 1; b <= n; b++) {
      edges.push(edge(a, b, 1 + ((a * 7 + b * 13) % 40)));
    }
  }
  return edges;
}

describe("strongNeighborLimit", () => {
  it("keeps fewer relationships per pet as the library grows", () => {
    expect(strongNeighborLimit(2)).toBe(3);
    expect(strongNeighborLimit(8)).toBe(3);
    expect(strongNeighborLimit(9)).toBe(2);
    expect(strongNeighborLimit(20)).toBe(2);
    expect(strongNeighborLimit(21)).toBe(1);
    expect(strongNeighborLimit(50)).toBe(1);
  });
});

describe("selectEdges", () => {
  it("keeps each pet's strongest relationships once, without duplicates", () => {
    const edges = [edge(1, 2, 40), edge(1, 3, 30), edge(1, 4, 20), edge(1, 5, 10), edge(2, 3, 5)];

    const selected = selectEdges(edges, 5, "strong", 1);

    // Pet 5's only edge (1-5) is kept via pet 5 even though pet 1 ranks it 4th.
    expect(selected.map((e) => edgeKey(e.a_id, e.b_id)).sort()).toEqual(
      ["1:2", "1:3", "1:4", "1:5", "2:3"].sort(),
    );
    expect(new Set(selected.map((e) => edgeKey(e.a_id, e.b_id))).size).toBe(selected.length);
  });

  it("suppresses extremely weak edges relative to the strongest", () => {
    const edges = [edge(1, 2, 100), edge(1, 3, 2), edge(2, 3, 50)];

    const selected = selectEdges(edges, 3, "strong", 1);

    expect(selected.map((e) => e.count)).toEqual([100, 50]);
  });

  it("bounds the default view for large libraries while 'all' shows everything", () => {
    const edges = completeEdges(50);

    const strong = selectEdges(edges, 50, "strong", 1);

    expect(edges).toHaveLength(1225);
    expect(strong.length).toBeLessThanOrEqual(50);
    expect(selectEdges(edges, 50, "all", 1)).toHaveLength(1225);
  });

  it("limits top25 to the 25 strongest", () => {
    const selected = selectEdges(completeEdges(20), 20, "top25", 1);

    expect(selected).toHaveLength(TOP_EDGE_LIMIT);
    expect(selected[0].count).toBeGreaterThanOrEqual(selected[24].count);
  });

  it("applies the minimum-together slider in every mode", () => {
    const edges = [edge(1, 2, 9), edge(1, 3, 3), edge(2, 3, 1)];

    for (const mode of ["strong", "top25", "all"] as const) {
      expect(selectEdges(edges, 3, mode, 3).every((e) => e.count >= 3)).toBe(true);
    }
  });

  it("returns nothing when there are no co-occurrences", () => {
    expect(selectEdges([], 5, "strong", 1)).toEqual([]);
  });
});

describe("backboneEdges", () => {
  it("is independent of weakness suppression so every connected pet keeps an edge", () => {
    const edges = [edge(1, 2, 100), edge(1, 3, 1)];

    const backbone = backboneEdges(edges, 3);

    expect(backbone.map((e) => edgeKey(e.a_id, e.b_id))).toContain("1:3");
  });
});

describe("rankPairs", () => {
  it("sorts by count, breaks ties by name, and caps the list", () => {
    const nodes = [node(1, "Fibs"), node(2, "Henri"), node(3, "Hermann"), node(4, "Mochi")];
    const edges = [edge(3, 4, 14), edge(1, 3, 39), edge(1, 2, 39), edge(2, 3, 37)];

    expect(rankPairs(edges, nodes, 3).map((e) => [e.a_id, e.b_id])).toEqual([
      [1, 2],
      [1, 3],
      [2, 3],
    ]);
  });
});

describe("nodeDiameter", () => {
  it("keeps thumbnails within the 48-64px band on wide screens", () => {
    expect(nodeDiameter(100, 100, 10, false)).toBe(64);
    expect(nodeDiameter(0, 100, 10, false)).toBe(48);
  });

  it("uses a smaller but still recognizable band on narrow screens", () => {
    expect(nodeDiameter(100, 100, 10, true)).toBe(52);
    expect(nodeDiameter(0, 100, 10, true)).toBe(40);
  });

  it("falls back to the middle of the band when no pet has photos", () => {
    expect(nodeDiameter(0, 0, 3, false)).toBe(56);
  });
});

describe("labelledNodeIds", () => {
  it("labels everyone in small libraries", () => {
    const nodes = Array.from({ length: 12 }, (_, i) => node(i + 1));

    expect(labelledNodeIds(nodes, []).size).toBe(12);
  });

  it("labels only the most connected pets in large libraries", () => {
    const nodes = Array.from({ length: 30 }, (_, i) => node(i + 1));
    const labelled = labelledNodeIds(nodes, [edge(29, 30, 99), edge(28, 29, 50)]);

    expect(labelled.size).toBe(12);
    expect(labelled.has(29)).toBe(true);
    expect(labelled.has(30)).toBe(true);
  });
});
