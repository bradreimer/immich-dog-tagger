import { describe, expect, it } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import { SpeciesTimelineChart } from "./SpeciesTimelineChart";
import type { SpeciesTimelinePoint } from "../../../types/metrics";

function yearPoints(count: number): SpeciesTimelinePoint[] {
  return Array.from({ length: count }, (_, i) => ({
    label: `${2000 + i}`,
    counts: { Fibs: i + 1, Fletch: (i % 3) + 1 },
  }));
}

describe("SpeciesTimelineChart", () => {
  it("renders one label per point with no downsampling for long histories", () => {
    const points = yearPoints(40);

    render(<SpeciesTimelineChart title="Dogs Over Time" identities={["Fibs", "Fletch"]} points={points} />);

    for (const point of points) {
      expect(screen.getByText(point.label)).toBeInTheDocument();
    }
  });

  it("renders X-axis labels horizontally, not rotated", () => {
    const points = yearPoints(8);

    const { container } = render(
      <SpeciesTimelineChart title="Dogs Over Time" identities={["Fibs", "Fletch"]} points={points} />,
    );

    const labels = container.querySelectorAll("svg text[text-anchor='middle']");
    expect(labels).toHaveLength(points.length);
    for (const label of labels) {
      expect(label).not.toHaveAttribute("transform");
    }
  });

  it("isolates one identity's data on legend click, then restores on a second click", () => {
    const points = yearPoints(4);

    render(<SpeciesTimelineChart title="Dogs Over Time" identities={["Fibs", "Fletch"]} points={points} />);

    const fibsLegendButton = screen.getByRole("button", { name: "Fibs" });
    fireEvent.click(fibsLegendButton);

    expect(fibsLegendButton).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("img")).toHaveAttribute("aria-label", expect.stringContaining("isolated to Fibs"));

    fireEvent.click(fibsLegendButton);

    expect(fibsLegendButton).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByRole("img")).not.toHaveAttribute("aria-label", expect.stringContaining("isolated"));
  });

  it("switches isolation directly from one identity to another", () => {
    const points = yearPoints(4);

    render(<SpeciesTimelineChart title="Dogs Over Time" identities={["Fibs", "Fletch"]} points={points} />);

    const fibsLegendButton = screen.getByRole("button", { name: "Fibs" });
    const fletchLegendButton = screen.getByRole("button", { name: "Fletch" });

    fireEvent.click(fibsLegendButton);
    fireEvent.click(fletchLegendButton);

    expect(fletchLegendButton).toHaveAttribute("aria-pressed", "true");
    expect(fibsLegendButton).toHaveAttribute("aria-pressed", "false");
  });

  it("renders a single-year history as a duplicated full-width point without erroring", () => {
    const points = yearPoints(1);

    render(<SpeciesTimelineChart title="Dogs Over Time" identities={["Fibs", "Fletch"]} points={points} />);

    expect(screen.getAllByText(points[0].label).length).toBeGreaterThan(0);
  });
});
