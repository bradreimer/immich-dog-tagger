import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen } from "@testing-library/react";

import * as api from "@/lib/api";
import type { PipelineJob } from "@/types/jobs";

import { LOOK_HARDER_POLL_MS, LookHarderButton } from "./LookHarderButton";

vi.mock("@/lib/api", () => ({
  lookHarder: vi.fn(),
  getJob: vi.fn(),
}));

function job(overrides: Partial<PipelineJob> = {}): PipelineJob {
  return {
    id: 9,
    operation: "look_harder",
    status: "pending",
    progress_current: 0,
    progress_total: null,
    progress_message: "Queued: Look harder",
    error_message: null,
    cancel_requested: false,
    created_at: "2026-10-03T00:00:00Z",
    started_at: null,
    completed_at: null,
    target_immich_asset_id: "asset-42",
    ...overrides,
  };
}

async function confirm() {
  fireEvent.click(screen.getByRole("button", { name: /look harder/i }));
  await act(async () => {
    fireEvent.click(screen.getByRole("button", { name: /yes, look harder/i }));
  });
}

async function advancePoll() {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(LOOK_HARDER_POLL_MS);
  });
}

describe("LookHarderButton", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.clearAllMocks();
  });

  it("asks for confirmation before starting", () => {
    render(<LookHarderButton immichAssetId="asset-42" available onFinished={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: /look harder/i }));

    expect(screen.getByText(/can take several minutes/i)).toBeInTheDocument();
    expect(api.lookHarder).not.toHaveBeenCalled();
  });

  it("is disabled when the detector isn't available", () => {
    render(
      <LookHarderButton immichAssetId="asset-42" available={false} onFinished={vi.fn()} />,
    );

    expect(screen.getByRole("button", { name: /look harder/i })).toBeDisabled();
  });

  it("polls the job until it completes, then reports its message", async () => {
    vi.mocked(api.lookHarder).mockResolvedValue(job());
    vi.mocked(api.getJob)
      .mockResolvedValueOnce(job({ status: "running", progress_message: "Looking harder" }))
      .mockResolvedValueOnce(
        job({ status: "completed", progress_message: "Look harder found 1 dog(s)" }),
      );
    const onFinished = vi.fn();

    render(<LookHarderButton immichAssetId="asset-42" available onFinished={onFinished} />);
    await confirm();

    expect(api.lookHarder).toHaveBeenCalledWith("asset-42");
    expect(screen.getByText(/queued/i)).toBeInTheDocument();

    await advancePoll();
    expect(screen.getByText("Looking harder")).toBeInTheDocument();
    expect(onFinished).not.toHaveBeenCalled();

    await advancePoll();
    expect(api.getJob).toHaveBeenCalledWith(9);
    expect(onFinished).toHaveBeenCalledWith("Look harder found 1 dog(s)");
    expect(screen.getByRole("button", { name: /look harder/i })).toBeEnabled();
  });

  it("shows the job's error when it fails", async () => {
    vi.mocked(api.lookHarder).mockResolvedValue(job());
    vi.mocked(api.getJob).mockResolvedValue(
      job({ status: "failed", error_message: "Look harder failed: boom" }),
    );
    const onFinished = vi.fn();

    render(<LookHarderButton immichAssetId="asset-42" available onFinished={onFinished} />);
    await confirm();
    await advancePoll();

    expect(screen.getByText("Look harder failed: boom")).toBeInTheDocument();
    expect(onFinished).not.toHaveBeenCalled();
  });

  it("shows an error when the job can't be started", async () => {
    vi.mocked(api.lookHarder).mockRejectedValue(new Error("Look harder isn't available"));

    render(<LookHarderButton immichAssetId="asset-42" available onFinished={vi.fn()} />);
    await confirm();

    expect(screen.getByText("Look harder isn't available")).toBeInTheDocument();
  });
});
