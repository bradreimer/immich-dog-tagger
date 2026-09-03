import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { JobQueuePage } from "./JobQueuePage";
import * as api from "@/lib/api";
import type { PipelineJob } from "@/types/jobs";

vi.mock("@/lib/api", () => ({
  getJobs: vi.fn(),
  getDiagnostics: vi.fn(),
  clearJobHistory: vi.fn(),
  cancelJob: vi.fn(),
}));

function buildJob(overrides: Partial<PipelineJob> = {}): PipelineJob {
  return {
    id: 1,
    operation: "scan",
    status: "completed",
    progress_current: 10,
    progress_total: 10,
    progress_message: null,
    error_message: null,
    cancel_requested: false,
    created_at: "2026-01-01T00:00:00Z",
    started_at: "2026-01-01T00:00:00Z",
    completed_at: "2026-01-01T00:01:00Z",
    ...overrides,
  };
}

describe("JobQueuePage", () => {
  beforeEach(() => {
    vi.mocked(api.getDiagnostics).mockRejectedValue(new Error("unavailable"));
  });

  it("asks for confirmation before clearing job history", async () => {
    vi.mocked(api.getJobs).mockResolvedValue([buildJob()]);

    render(<JobQueuePage />);

    const clearButton = await screen.findByRole("button", { name: "Clear list" });
    fireEvent.click(clearButton);

    expect(screen.getByRole("button", { name: "Yes, clear list" })).toBeInTheDocument();
    expect(api.clearJobHistory).not.toHaveBeenCalled();
  });

  it("cancels back to the plain button without clearing", async () => {
    vi.mocked(api.getJobs).mockResolvedValue([buildJob()]);

    render(<JobQueuePage />);

    fireEvent.click(await screen.findByRole("button", { name: "Clear list" }));
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));

    expect(screen.getByRole("button", { name: "Clear list" })).toBeInTheDocument();
    expect(api.clearJobHistory).not.toHaveBeenCalled();
  });

  it("clears job history once confirmed", async () => {
    vi.mocked(api.getJobs).mockResolvedValue([buildJob()]);
    vi.mocked(api.clearJobHistory).mockResolvedValue({ cleared: 1 });

    render(<JobQueuePage />);

    fireEvent.click(await screen.findByRole("button", { name: "Clear list" }));
    fireEvent.click(screen.getByRole("button", { name: "Yes, clear list" }));

    await waitFor(() => expect(api.clearJobHistory).toHaveBeenCalled());
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Clear list" })).toBeInTheDocument(),
    );
  });
});
