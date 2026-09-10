import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { JobQueuePage } from "./JobQueuePage";
import * as api from "@/lib/api";
import type { PipelineJob } from "@/types/jobs";
import type { Diagnostics } from "@/types/diagnostics";

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

function buildDiagnostics(overrides: Partial<Diagnostics> = {}): Diagnostics {
  return {
    db: { healthy: true },
    scheduler: null,
    jobs: {
      counts: {},
      stuck_threshold_seconds: 300,
      stuck: [],
      recent_failures: [],
    },
    backup: { last_backup_at: null, backup_count: 0, has_backup: false },
    derived_data: {
      healthy: true,
      missing_downloads: 0,
      missing_crops: 0,
      missing_embedding_sources: 0,
      total_missing: 0,
    },
    stale_detections: { healthy: true, flagged: 0, reviewed_at_risk: 0 },
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

  it("renders a URL in a job's error_message as a clickable link", async () => {
    vi.mocked(api.getJobs).mockResolvedValue([
      buildJob({
        status: "failed",
        error_message:
          "No permission. See https://github.com/bradreimer/immich-dog-tagger/docs/immich-api-key-permissions.md for details.",
      }),
    ]);

    render(<JobQueuePage />);

    const link = await screen.findByRole("link", {
      name: "https://github.com/bradreimer/immich-dog-tagger/docs/immich-api-key-permissions.md",
    });
    expect(link).toHaveAttribute(
      "href",
      "https://github.com/bradreimer/immich-dog-tagger/docs/immich-api-key-permissions.md",
    );
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noreferrer");
    expect(screen.getByText(/No permission\. See/)).toBeInTheDocument();
  });

  it("renders a job's error_message unchanged when it has no URL", async () => {
    vi.mocked(api.getJobs).mockResolvedValue([
      buildJob({ status: "failed", error_message: "Something went wrong." }),
    ]);

    render(<JobQueuePage />);

    expect(await screen.findByText("Error: Something went wrong.")).toBeInTheDocument();
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });

  it("renders a URL in the Recent Failures card as a clickable link", async () => {
    vi.mocked(api.getJobs).mockResolvedValue([]);
    vi.mocked(api.getDiagnostics).mockResolvedValue(
      buildDiagnostics({
        jobs: {
          counts: {},
          stuck_threshold_seconds: 300,
          stuck: [],
          recent_failures: [
            {
              id: 5,
              operation: "sync",
              error_message: "Failed. See https://example.com/docs for help.",
              completed_at: "2026-01-01T00:00:00Z",
            },
          ],
        },
      }),
    );

    render(<JobQueuePage />);

    const link = await screen.findByRole("link", { name: "https://example.com/docs" });
    expect(link).toHaveAttribute("href", "https://example.com/docs");
  });
});
