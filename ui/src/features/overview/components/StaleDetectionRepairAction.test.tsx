import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { StaleDetectionRepairAction } from "./StaleDetectionRepairAction";
import * as api from "@/lib/api";
import type { StaleDetectionRepairResult, StaleDetectionStatus } from "@/types/diagnostics";

vi.mock("@/lib/api", () => ({
  repairStaleDetections: vi.fn(),
}));

function buildStatus(overrides: Partial<StaleDetectionStatus> = {}): StaleDetectionStatus {
  return {
    healthy: false,
    flagged: 3,
    reviewed_at_risk: 1,
    ...overrides,
  };
}

function buildResult(
  overrides: Partial<StaleDetectionRepairResult> = {},
): StaleDetectionRepairResult {
  return {
    repaired: 2,
    skipped_reviewed: 1,
    failed: 0,
    ...overrides,
  };
}

describe("StaleDetectionRepairAction", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("renders nothing when healthy", () => {
    const { container } = render(
      <StaleDetectionRepairAction status={buildStatus({ healthy: true, flagged: 0 })} onRepaired={vi.fn()} />,
    );

    expect(container).toBeEmptyDOMElement();
  });

  it("asks for confirmation before repairing, with the opt-in switch unchecked", () => {
    render(<StaleDetectionRepairAction status={buildStatus()} onRepaired={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: "Repair" }));

    const toggle = screen.getByRole("switch");
    expect(toggle).toHaveAttribute("aria-checked", "false");
    expect(api.repairStaleDetections).not.toHaveBeenCalled();
  });

  it("repairs excluding reviewed photos by default", async () => {
    const result = buildResult();
    vi.mocked(api.repairStaleDetections).mockResolvedValue(result);
    const onRepaired = vi.fn();

    render(<StaleDetectionRepairAction status={buildStatus()} onRepaired={onRepaired} />);

    fireEvent.click(screen.getByRole("button", { name: "Repair" }));
    fireEvent.click(screen.getByRole("button", { name: /yes, repair/i }));

    await waitFor(() => expect(onRepaired).toHaveBeenCalled());
    expect(api.repairStaleDetections).toHaveBeenCalledWith(false);
  });

  it("repairs including reviewed photos once the switch is opted in", async () => {
    vi.mocked(api.repairStaleDetections).mockResolvedValue(buildResult());

    render(<StaleDetectionRepairAction status={buildStatus()} onRepaired={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: "Repair" }));
    fireEvent.click(screen.getByRole("switch"));
    fireEvent.click(screen.getByRole("button", { name: /yes, repair/i }));

    await waitFor(() =>
      expect(api.repairStaleDetections).toHaveBeenCalledWith(true),
    );
  });

  it("cancels back to the plain button without repairing", () => {
    render(<StaleDetectionRepairAction status={buildStatus()} onRepaired={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: "Repair" }));
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));

    expect(screen.getByRole("button", { name: "Repair" })).toBeInTheDocument();
    expect(api.repairStaleDetections).not.toHaveBeenCalled();
  });

  it("does not show the opt-in switch when nothing reviewed is at risk", () => {
    render(
      <StaleDetectionRepairAction
        status={buildStatus({ reviewed_at_risk: 0 })}
        onRepaired={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Repair" }));

    expect(screen.queryByRole("switch")).not.toBeInTheDocument();
  });

  it("shows the before/after flagged count when a repair actually reduces it", async () => {
    vi.mocked(api.repairStaleDetections).mockResolvedValue(
      buildResult({ repaired: 2, skipped_reviewed: 1, failed: 0 }),
    );

    const { rerender } = render(
      <StaleDetectionRepairAction status={buildStatus({ flagged: 3 })} onRepaired={vi.fn()} />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Repair" }));
    fireEvent.click(screen.getByRole("button", { name: /yes, repair/i }));

    await waitFor(() => expect(api.repairStaleDetections).toHaveBeenCalled());

    // Simulate the parent's diagnostics reload landing with a lower count.
    rerender(
      <StaleDetectionRepairAction status={buildStatus({ flagged: 1 })} onRepaired={vi.fn()} />,
    );

    const summary = await screen.findByText(/3 → 1 still flagged/);
    expect(summary).toHaveTextContent(
      "Repaired 2, skipped 1 reviewed, failed 0 — 3 → 1 still flagged.",
    );
    expect(summary.className).not.toContain("text-status-warning");
  });

  it("flags a warning when the flagged count doesn't drop as expected", async () => {
    vi.mocked(api.repairStaleDetections).mockResolvedValue(
      buildResult({ repaired: 2, skipped_reviewed: 0, failed: 0 }),
    );

    const { rerender } = render(
      <StaleDetectionRepairAction status={buildStatus({ flagged: 3 })} onRepaired={vi.fn()} />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Repair" }));
    fireEvent.click(screen.getByRole("button", { name: /yes, repair/i }));

    await waitFor(() => expect(api.repairStaleDetections).toHaveBeenCalled());

    // The count didn't move even though 2 were reported repaired.
    rerender(
      <StaleDetectionRepairAction status={buildStatus({ flagged: 3 })} onRepaired={vi.fn()} />,
    );

    const summary = await screen.findByText(/3 → 3 still flagged/);
    expect(summary.className).toContain("text-status-warning");
  });

  it("keeps showing the result summary even after a full repair flips status healthy", async () => {
    vi.mocked(api.repairStaleDetections).mockResolvedValue(
      buildResult({ repaired: 3, skipped_reviewed: 0, failed: 0 }),
    );

    const { rerender } = render(
      <StaleDetectionRepairAction status={buildStatus({ flagged: 3 })} onRepaired={vi.fn()} />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Repair" }));
    fireEvent.click(screen.getByRole("button", { name: /yes, repair/i }));

    await waitFor(() => expect(api.repairStaleDetections).toHaveBeenCalled());

    rerender(
      <StaleDetectionRepairAction
        status={buildStatus({ healthy: true, flagged: 0 })}
        onRepaired={vi.fn()}
      />,
    );

    expect(await screen.findByText(/3 → 0 still flagged/)).toBeInTheDocument();
  });

  it("shows an error and stays in the confirm state when repair fails", async () => {
    vi.mocked(api.repairStaleDetections).mockRejectedValue(
      new Error("Failed to repair stale detections"),
    );
    const onRepaired = vi.fn();

    render(<StaleDetectionRepairAction status={buildStatus()} onRepaired={onRepaired} />);

    fireEvent.click(screen.getByRole("button", { name: "Repair" }));
    fireEvent.click(screen.getByRole("button", { name: /yes, repair/i }));

    expect(await screen.findByText("Failed to repair stale detections")).toBeInTheDocument();
    expect(onRepaired).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: /yes, repair/i })).toBeInTheDocument();
  });
});
