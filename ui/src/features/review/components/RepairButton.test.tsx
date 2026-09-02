import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { RepairButton } from "./RepairButton";
import * as api from "@/lib/api";
import type { AssetRepairResult } from "@/types/photoLookup";

vi.mock("@/lib/api", () => ({
  repairAsset: vi.fn(),
}));

function buildResult(overrides: Partial<AssetRepairResult> = {}): AssetRepairResult {
  return {
    asset_id: 1,
    immich_asset_id: "asset-42",
    status: "detected",
    detections: 1,
    dogs: 1,
    cats: 0,
    classified: 1,
    message: "Repaired: 1 detection(s) found, 1 classified.",
    ...overrides,
  };
}

describe("RepairButton", () => {
  it("renders nothing without an Immich asset id", () => {
    const { container } = render(
      <RepairButton immichAssetId={null} onRepaired={vi.fn()} />,
    );

    expect(container).toBeEmptyDOMElement();
  });

  it("asks for confirmation before repairing", () => {
    render(<RepairButton immichAssetId="asset-42" onRepaired={vi.fn()} />);

    expect(screen.queryByText(/discards any review/i)).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Repair" }));

    expect(screen.getByText(/discards any review/i)).toBeInTheDocument();
    expect(api.repairAsset).not.toHaveBeenCalled();
  });

  it("cancels back to the plain button without repairing", () => {
    render(<RepairButton immichAssetId="asset-42" onRepaired={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: "Repair" }));
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));

    expect(screen.getByRole("button", { name: "Repair" })).toBeInTheDocument();
    expect(api.repairAsset).not.toHaveBeenCalled();
  });

  it("repairs the asset and reports the result once confirmed", async () => {
    const result = buildResult();
    vi.mocked(api.repairAsset).mockResolvedValue(result);
    const onRepaired = vi.fn();

    render(<RepairButton immichAssetId="asset-42" onRepaired={onRepaired} />);

    fireEvent.click(screen.getByRole("button", { name: "Repair" }));
    fireEvent.click(screen.getByRole("button", { name: /yes, repair/i }));

    await waitFor(() => expect(onRepaired).toHaveBeenCalledWith(result));

    expect(api.repairAsset).toHaveBeenCalledWith("asset-42");
    expect(screen.getByRole("button", { name: "Repair" })).toBeInTheDocument();
  });

  it("shows an error and stays in the confirm state when repair fails", async () => {
    vi.mocked(api.repairAsset).mockRejectedValue(new Error("Failed to repair photo"));
    const onRepaired = vi.fn();

    render(<RepairButton immichAssetId="asset-42" onRepaired={onRepaired} />);

    fireEvent.click(screen.getByRole("button", { name: "Repair" }));
    fireEvent.click(screen.getByRole("button", { name: /yes, repair/i }));

    expect(await screen.findByText("Failed to repair photo")).toBeInTheDocument();
    expect(onRepaired).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: /yes, repair/i })).toBeInTheDocument();
  });
});
