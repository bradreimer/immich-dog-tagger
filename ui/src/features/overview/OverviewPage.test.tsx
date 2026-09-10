import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { OverviewPage } from "./OverviewPage";
import * as api from "../../lib/api";
import type { PipelineJob } from "../../types/jobs";
import type { ReviewQueueStats } from "../../types/review";

vi.mock("../../lib/api", () => ({
  createJob: vi.fn(),
  getDiagnostics: vi.fn(),
  getJobs: vi.fn(),
  getReviewStats: vi.fn(),
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

const stats: ReviewQueueStats = {
  total: 10,
  reviewed: 8,
  remaining: 2,
};

describe("OverviewPage", () => {
  beforeEach(() => {
    vi.mocked(api.getJobs).mockResolvedValue([buildJob()]);
    vi.mocked(api.getReviewStats).mockResolvedValue(stats);
    vi.mocked(api.getDiagnostics).mockRejectedValue(new Error("unavailable"));
  });

  it("does not render a per-job list", async () => {
    render(<OverviewPage />);

    await waitFor(() => expect(api.getJobs).toHaveBeenCalled());

    expect(screen.queryByText("Recent Jobs")).not.toBeInTheDocument();
    expect(screen.queryByText(/^#1 Scan$/)).not.toBeInTheDocument();
  });

  it("navigates to Job Queue when View all jobs is clicked", async () => {
    render(<OverviewPage />);

    const link = await screen.findByRole("button", { name: "View all jobs" });

    const pushStateSpy = vi.spyOn(window.history, "pushState");
    fireEvent.click(link);

    expect(pushStateSpy).toHaveBeenCalledWith({}, "", "/jobs");
    pushStateSpy.mockRestore();
  });

  it("still shows the summary stat tiles", async () => {
    render(<OverviewPage />);

    expect(await screen.findByText("Active Jobs")).toBeInTheDocument();
    expect(screen.getByText("Completed")).toBeInTheDocument();
    expect(screen.getByText("Failed")).toBeInTheDocument();
    expect(screen.getByText("Review Remaining")).toBeInTheDocument();
  });

  it("launches a learn job from Manual Operations, matching Settings' wording", async () => {
    vi.mocked(api.createJob).mockResolvedValue(buildJob({ id: 7, operation: "learn" }));

    render(<OverviewPage />);

    expect(await screen.findByText("Learn from reviewed examples")).toBeInTheDocument();
    expect(
      screen.getByText(
        "Fold recent review corrections into the reference set the classifier uses for future predictions.",
      ),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Learn from reviewed examples" }));

    await waitFor(() => expect(api.createJob).toHaveBeenCalledWith("learn"));
  });

  it("has no header job-launch shortcuts, only the refresh control", async () => {
    render(<OverviewPage />);

    await screen.findByRole("button", { name: "Refresh dashboard" });

    expect(screen.queryByRole("button", { name: "Run Pipeline" })).not.toBeInTheDocument();
    // "Reclassify" (bare, no aria-label) was the header shortcut's accessible
    // name; the Manual Operations card's equivalent has a longer aria-label
    // ("Reclassify existing photos with reviewed examples"), so this exact
    // name match is unambiguous.
    expect(screen.queryByRole("button", { name: "Reclassify" })).not.toBeInTheDocument();

    expect(
      screen.getByRole("button", { name: "Reclassify existing photos with reviewed examples" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Run the full pipeline" })).toBeInTheDocument();
  });
});
