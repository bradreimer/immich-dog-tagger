import { describe, expect, it } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";

import type { FriendEdge, FriendNode, FriendsInFrame as FriendsData } from "../../../types/metrics";
import { FriendsInFrame } from "./FriendsInFrame";
import { INITIAL_PAIR_COUNT, MAX_PAIR_COUNT } from "./MostCommonPairs";

function pet(id: number, name: string, imageCount = 20, keyCrop: number | null = id * 10): FriendNode {
  return { id, name, species: "dog", image_count: imageCount, key_crop_id: keyCrop };
}

function edge(a: number, b: number, count: number): FriendEdge {
  return { a_id: a, b_id: b, count };
}

function manyPets(n: number): FriendNode[] {
  return Array.from({ length: n }, (_, i) => pet(i + 1, `Pet${String(i + 1).padStart(2, "0")}`));
}

const trio: FriendsData = {
  nodes: [pet(1, "Fibs"), pet(2, "Henri"), pet(3, "Hermann")],
  edges: [edge(1, 2, 42), edge(1, 3, 39), edge(2, 3, 37)],
};

describe("FriendsInFrame states", () => {
  it("shows a friendly message when there are no pets", () => {
    render(<FriendsInFrame data={{ nodes: [], edges: [] }} />);

    expect(screen.getByText("Friends in Frame")).toBeInTheDocument();
    expect(screen.getByText("Which animals tend to appear together in your photos?")).toBeInTheDocument();
    expect(screen.getByText(/No pets yet/)).toBeInTheDocument();
  });

  it("shows no pairs section for a single pet or pets that share no photos", () => {
    const { unmount } = render(<FriendsInFrame data={{ nodes: [pet(1, "Fibs")], edges: [] }} />);
    expect(screen.queryByText("Most Common Pairs")).not.toBeInTheDocument();
    unmount();

    render(<FriendsInFrame data={{ nodes: [pet(1, "Fibs"), pet(2, "Henri")], edges: [] }} />);
    expect(screen.queryByText("Most Common Pairs")).not.toBeInTheDocument();
  });

  it("hovering a pair card lights its edge in the network", () => {
    const nodes = [pet(1, "Fibs"), pet(2, "Henri"), pet(3, "Hermann"), pet(4, "Mochi")];
    render(
      <FriendsInFrame
        data={{ nodes, edges: [edge(1, 2, 42), edge(1, 3, 39), edge(2, 3, 37), edge(3, 4, 5)] }}
      />,
    );

    // Only the three strongest edges carry a count at rest.
    expect(screen.queryByText("5")).not.toBeInTheDocument();

    fireEvent.mouseEnter(screen.getAllByRole("listitem")[3]);

    expect(screen.getByText("5")).toBeInTheDocument();
  });
});

describe("Most Common Pairs", () => {
  it("ranks pairs by co-occurrence count with names and counts", () => {
    render(<FriendsInFrame data={trio} />);

    const items = screen.getAllByRole("listitem");
    expect(items).toHaveLength(3);
    expect(within(items[0]).getByText("Fibs + Henri")).toBeInTheDocument();
    expect(within(items[0]).getByText("42 images together")).toBeInTheDocument();
    expect(within(items[1]).getByText("Fibs + Hermann")).toBeInTheDocument();
    expect(within(items[2]).getByText("Henri + Hermann")).toBeInTheDocument();
  });

  it("shows the top six first and expands up to the cap, never hundreds", () => {
    const nodes = manyPets(30);
    const edges: FriendEdge[] = [];
    for (let a = 1; a <= 30; a++) {
      for (let b = a + 1; b <= 30; b++) {
        edges.push(edge(a, b, 1 + ((a * 7 + b * 13) % 40)));
      }
    }
    render(<FriendsInFrame data={{ nodes, edges }} />);

    expect(screen.getAllByRole("listitem")).toHaveLength(INITIAL_PAIR_COUNT);

    fireEvent.click(screen.getByRole("button", { name: /^Show more \(24\)/ }));
    expect(screen.getAllByRole("listitem")).toHaveLength(MAX_PAIR_COUNT);

    fireEvent.click(screen.getByRole("button", { name: "Show fewer" }));
    expect(screen.getAllByRole("listitem")).toHaveLength(INITIAL_PAIR_COUNT);
  });

  it("does not offer 'show more' when every pair already fits", () => {
    render(<FriendsInFrame data={trio} />);

    expect(screen.queryByRole("button", { name: /Show more \(/ })).not.toBeInTheDocument();
  });

  it("uses singular wording for one image", () => {
    render(<FriendsInFrame data={{ nodes: [pet(1, "Fibs"), pet(2, "Henri")], edges: [edge(1, 2, 1)] }} />);

    expect(screen.getByText("1 image together")).toBeInTheDocument();
  });
});
