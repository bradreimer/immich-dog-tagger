import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";

import type { FriendEdge, FriendNode, FriendsInFrame as FriendsData } from "../../../types/metrics";
import { FriendsNetwork } from "./FriendsNetwork";

function FriendsInFrame({ data, onNavigate }: { data: FriendsData; onNavigate?: (path: string) => void }) {
  return <FriendsNetwork nodes={data.nodes} edges={data.edges} onNavigate={onNavigate} />;
}

function pet(id: number, name: string, imageCount = 20, keyCrop: number | null = id * 10): FriendNode {
  return { id, name, species: "dog", image_count: imageCount, key_crop_id: keyCrop };
}

function edge(a: number, b: number, count: number): FriendEdge {
  return { a_id: a, b_id: b, count };
}

function manyPets(n: number): FriendNode[] {
  return Array.from({ length: n }, (_, i) => pet(i + 1, `Pet${String(i + 1).padStart(2, "0")}`));
}

function ringEdges(n: number): FriendEdge[] {
  return Array.from({ length: n }, (_, i) => edge(i + 1, ((i + 1) % n) + 1, 5 + i));
}

const trio: FriendsData = {
  nodes: [pet(1, "Fibs"), pet(2, "Henri"), pet(3, "Hermann")],
  edges: [edge(1, 2, 42), edge(1, 3, 39), edge(2, 3, 37)],
};

describe("FriendsNetwork states", () => {
  it("shows a single pet with 'No relationships yet'", () => {
    render(<FriendsInFrame data={{ nodes: [pet(1, "Fibs")], edges: [] }} />);

    expect(screen.getByRole("button", { name: /Fibs/ })).toBeInTheDocument();
    expect(screen.getByText("No relationships yet")).toBeInTheDocument();
  });

  it("shows two pets with their relationship and no controls", () => {
    render(
      <FriendsInFrame
        data={{ nodes: [pet(1, "Fibs"), pet(2, "Henri")], edges: [edge(1, 2, 7)] }}
      />,
    );

    expect(screen.getByRole("button", { name: /Fibs/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Henri/ })).toBeInTheDocument();
    expect(screen.getByTestId("edge-1:2")).toBeInTheDocument();
    expect(screen.queryByRole("group", { name: "Connections to show" })).not.toBeInTheDocument();
  });

  it("explains when pets share no photos yet, without drawing edges", () => {
    render(<FriendsInFrame data={{ nodes: [pet(1, "Fibs"), pet(2, "Henri")], edges: [] }} />);

    expect(screen.getByText(/No shared appearances yet/)).toBeInTheDocument();
    expect(screen.getAllByRole("button")).toHaveLength(2);
  });

  it("falls back to the pet's initial when it has no key thumbnail", () => {
    render(<FriendsInFrame data={{ nodes: [pet(1, "Fibs", 3, null)], edges: [] }} />);

    expect(screen.getByRole("button", { name: /Fibs/ }).querySelector("img")).toBeNull();
    expect(screen.getAllByText("F").length).toBeGreaterThan(0);
  });

  it("falls back to the initial when the thumbnail fails to load", () => {
    render(<FriendsInFrame data={{ nodes: [pet(1, "Fibs")], edges: [] }} />);

    const image = screen.getByRole("button", { name: /Fibs/ }).querySelector("img")!;
    expect(image).toHaveAttribute("src", "/api/crops/10");
    fireEvent.error(image);

    expect(screen.getByRole("button", { name: /Fibs/ }).querySelector("img")).toBeNull();
  });
});

describe("FriendsNetwork", () => {
  it("renders every pet and reports the connection count", () => {
    render(<FriendsInFrame data={trio} />);

    for (const name of ["Fibs", "Henri", "Hermann"]) {
      expect(screen.getByRole("button", { name: new RegExp(name) })).toBeInTheDocument();
    }
    expect(screen.getByText("Showing 3 of 3 connections")).toBeInTheDocument();
  });

  it("does not render a legend", () => {
    render(<FriendsInFrame data={trio} />);

    expect(screen.queryByText(/legend/i)).not.toBeInTheDocument();
  });

  it("shows a tooltip with names, the count and each side's share on edge hover", () => {
    render(<FriendsInFrame data={trio} />);

    fireEvent.mouseMove(screen.getByTestId("edge-1:2"), { clientX: 100, clientY: 100 });

    const tooltip = screen.getByRole("tooltip");
    expect(within(tooltip).getByText("Fibs + Henri")).toBeInTheDocument();
    expect(within(tooltip).getByText("42 images together")).toBeInTheDocument();
    expect(within(tooltip).getByText(/% of Fibs's photos/)).toBeInTheDocument();

    fireEvent.mouseLeave(screen.getByTestId("edge-1:2"));
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
  });

  it("omits the percentage when a pet has no counted photos", () => {
    render(
      <FriendsInFrame
        data={{
          nodes: [pet(1, "Fibs", 0), pet(2, "Henri", 0), pet(3, "Hermann", 0)],
          edges: [edge(1, 2, 2)],
        }}
      />,
    );

    fireEvent.mouseMove(screen.getByTestId("edge-1:2"));

    expect(within(screen.getByRole("tooltip")).getByText("2 images together")).toBeInTheDocument();
    expect(screen.queryByText(/% of/)).not.toBeInTheDocument();
  });

  it("shows counts on a hovered pet's connections", () => {
    render(<FriendsInFrame data={{ ...trio, edges: [edge(1, 2, 42), edge(1, 3, 39), edge(2, 3, 11)] }} />);

    // At rest only the strongest edges carry a count; hovering reveals Fibs' own.
    fireEvent.mouseEnter(screen.getByRole("button", { name: /^Fibs/ }));

    expect(screen.getAllByText("42").length).toBeGreaterThan(0);
    expect(screen.getAllByText("39").length).toBeGreaterThan(0);
  });

  it("focuses on a clicked pet and returns with the Back button", () => {
    const onNavigate = vi.fn();
    render(<FriendsInFrame data={trio} onNavigate={onNavigate} />);

    fireEvent.click(screen.getByRole("button", { name: /^Fibs/ }));

    expect(screen.getByText(/Focused on/)).toBeInTheDocument();
    expect(screen.getByText(/2 friends in frame/)).toBeInTheDocument();
    expect(screen.queryByText(/Showing \d+ of/)).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Insights" }));
    expect(onNavigate).toHaveBeenCalledWith("/dogs/1/insights");

    fireEvent.click(screen.getByRole("button", { name: "Back to all friends" }));
    expect(screen.queryByText(/Focused on/)).not.toBeInTheDocument();
  });

  it("returns from focus with Escape", () => {
    render(<FriendsInFrame data={trio} />);

    fireEvent.click(screen.getByRole("button", { name: /^Fibs/ }));
    expect(screen.getByText(/Focused on/)).toBeInTheDocument();

    fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.queryByText(/Focused on/)).not.toBeInTheDocument();
  });

  it("keeps every pet visible and bounds the default edges in a large library", () => {
    const nodes = manyPets(30);
    const edges: FriendEdge[] = [];
    for (let a = 1; a <= 30; a++) {
      for (let b = a + 1; b <= 30; b++) {
        edges.push(edge(a, b, 1 + ((a * 7 + b * 13) % 40)));
      }
    }
    render(<FriendsInFrame data={{ nodes, edges }} />);

    expect(screen.getAllByRole("button", { name: /^Pet\d\d, / })).toHaveLength(30);
    const shown = Number(/Showing (\d+) of 435/.exec(document.body.textContent ?? "")?.[1]);
    expect(shown).toBeGreaterThan(0);
    expect(shown).toBeLessThanOrEqual(30);

    fireEvent.click(screen.getByRole("button", { name: "Show more connections" }));
    expect(screen.getByText("Showing 435 of 435 connections")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Show fewer connections" }));
    expect(screen.queryByText("Showing 435 of 435 connections")).not.toBeInTheDocument();
  });

  it("switches to Top 25 and applies the minimum-together slider", () => {
    const nodes = manyPets(12);
    render(<FriendsInFrame data={{ nodes, edges: ringEdges(12) }} />);

    fireEvent.click(screen.getByRole("button", { name: "Top 25" }));
    expect(screen.getByText("Showing 12 of 12 connections")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Minimum images together"), { target: { value: "10" } });
    expect(screen.getByText(/together in 10\+ images/)).toBeInTheDocument();
    expect(screen.getByText(/Showing 7 of 7 connections/)).toBeInTheDocument();
  });

  it("marks pets with no visible strong connections without hiding them", () => {
    const nodes = [pet(1, "Fibs"), pet(2, "Henri"), pet(3, "Hermann"), pet(4, "Mochi")];
    render(<FriendsInFrame data={{ nodes, edges: [edge(1, 2, 20), edge(1, 3, 15)] }} />);

    expect(screen.getByRole("button", { name: /^Mochi/ })).toBeInTheDocument();
    expect(screen.getByText("No shared photos")).toBeInTheDocument();
  });
});
