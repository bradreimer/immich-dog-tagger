import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { DerivedDataRepairAction } from "./DerivedDataRepairAction";
import * as api from "@/lib/api";
import type { DerivedDataRepairResult, DerivedDataStatus } from "@/types/diagnostics";

vi.mock("@/lib/api", () => ({
  repairDerivedData: vi.fn(),
}));

function buildStatus(overrides: Partial<DerivedDataStatus> = {}): DerivedDataStatus {
  return {
    healthy: false,
    missing_downloads: 1,
    missing_crops: 2,
    missing_embedding_sources: 0,
    total_missing: 3,
    reviewed_at_risk: 1,
    ...overrides,
  };
}

function buildResult(
  overrides: Partial<DerivedDataRepairResult> = {},
): DerivedDataRepairResult {
  return {
    downloads_repaired: 1,
    crops_repaired: 2,
    failed: 0,
    total_repaired: 3,
    ...overrides,
  };
}

describe("DerivedDataRepairAction", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("renders nothing when nothing is repair-eligible", () => {
    const { container } = render(
      <DerivedDataRepairAction
        status={buildStatus({ missing_downloads: 0, missing_crops: 0 })}
        onRepaired={vi.fn()}
      />,
    );

    expect(container).toBeEmptyDOMElement();
  });

  it("renders nothing when only embedding sources are missing", () => {
    // repair() can't fix missing embedding sources (needs a human re-run of
    // learn/import-review), so the action shouldn't offer a Repair button
    // that would do nothing.
    const { container } = render(
      <DerivedDataRepairAction
        status={buildStatus({
          missing_downloads: 0,
          missing_crops: 0,
          missing_embedding_sources: 4,
          total_missing: 4,
        })}
        onRepaired={vi.fn()}
      />,
    );

    expect(container).toBeEmptyDOMElement();
  });

  it("asks for confirmation before repairing", () => {
    render(<DerivedDataRepairAction status={buildStatus()} onRepaired={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: "Repair" }));

    expect(screen.getByRole("button", { name: /yes, repair/i })).toBeInTheDocument();
    expect(api.repairDerivedData).not.toHaveBeenCalled();
  });

  it("states the review-history-at-risk count in the confirmation", () => {
    render(
      <DerivedDataRepairAction
        status={buildStatus({ reviewed_at_risk: 2 })}
        onRepaired={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Repair" }));

    expect(screen.getByText(/2/)).toBeInTheDocument();
    expect(screen.getByText(/recorded review history that will be discarded/)).toBeInTheDocument();
  });

  it("omits the review-history warning when nothing reviewed is at risk", () => {
    render(
      <DerivedDataRepairAction
        status={buildStatus({ reviewed_at_risk: 0 })}
        onRepaired={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Repair" }));

    expect(
      screen.queryByText(/recorded review history that will be discarded/),
    ).not.toBeInTheDocument();
  });

  it("repairs once confirmed", async () => {
    vi.mocked(api.repairDerivedData).mockResolvedValue(buildResult());
    const onRepaired = vi.fn();

    render(<DerivedDataRepairAction status={buildStatus()} onRepaired={onRepaired} />);

    fireEvent.click(screen.getByRole("button", { name: "Repair" }));
    fireEvent.click(screen.getByRole("button", { name: /yes, repair/i }));

    await waitFor(() => expect(onRepaired).toHaveBeenCalled());
    expect(api.repairDerivedData).toHaveBeenCalled();
  });

  it("cancels back to the plain button without repairing", () => {
    render(<DerivedDataRepairAction status={buildStatus()} onRepaired={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: "Repair" }));
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));

    expect(screen.getByRole("button", { name: "Repair" })).toBeInTheDocument();
    expect(api.repairDerivedData).not.toHaveBeenCalled();
  });

  it("shows the before/after eligible count when a repair actually reduces it", async () => {
    vi.mocked(api.repairDerivedData).mockResolvedValue(buildResult());

    const { rerender } = render(
      <DerivedDataRepairAction
        status={buildStatus({ missing_downloads: 1, missing_crops: 2 })}
        onRepaired={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Repair" }));
    fireEvent.click(screen.getByRole("button", { name: /yes, repair/i }));

    await waitFor(() => expect(api.repairDerivedData).toHaveBeenCalled());

    // Simulate the parent's diagnostics reload landing with a lower count.
    rerender(
      <DerivedDataRepairAction
        status={buildStatus({ missing_downloads: 0, missing_crops: 0 })}
        onRepaired={vi.fn()}
      />,
    );

    const summary = await screen.findByText(/3 → 0 still missing/);
    expect(summary).toHaveTextContent(
      "Repaired 3 (1 download, 2 crops), failed 0 — 3 → 0 still missing.",
    );
    expect(summary.className).not.toContain("text-status-warning");
  });

  it("flags a warning when the eligible count doesn't drop as expected", async () => {
    vi.mocked(api.repairDerivedData).mockResolvedValue(buildResult());

    const { rerender } = render(
      <DerivedDataRepairAction
        status={buildStatus({ missing_downloads: 1, missing_crops: 2 })}
        onRepaired={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Repair" }));
    fireEvent.click(screen.getByRole("button", { name: /yes, repair/i }));

    await waitFor(() => expect(api.repairDerivedData).toHaveBeenCalled());

    // The count didn't move even though 3 were reported repaired.
    rerender(
      <DerivedDataRepairAction
        status={buildStatus({ missing_downloads: 1, missing_crops: 2 })}
        onRepaired={vi.fn()}
      />,
    );

    const summary = await screen.findByText(/3 → 3 still missing/);
    expect(summary.className).toContain("text-status-warning");
  });

  it("shows an error and stays in the confirm state when repair fails", async () => {
    vi.mocked(api.repairDerivedData).mockRejectedValue(
      new Error("Failed to repair derived data"),
    );
    const onRepaired = vi.fn();

    render(<DerivedDataRepairAction status={buildStatus()} onRepaired={onRepaired} />);

    fireEvent.click(screen.getByRole("button", { name: "Repair" }));
    fireEvent.click(screen.getByRole("button", { name: /yes, repair/i }));

    expect(await screen.findByText("Failed to repair derived data")).toBeInTheDocument();
    expect(onRepaired).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: /yes, repair/i })).toBeInTheDocument();
  });
});
