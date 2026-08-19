import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

import { MetricsPage } from "./MetricsPage";
import type { LearningMetrics } from "../../types/metrics";

const metrics: LearningMetrics = {
  eligible_count: 4,
  reviewed_count: 1,
  labeled_example_count: 3,
  confident_count: 2,
  needs_review_count: 1,
  unknown_count: 1,
  coverage: 0.5,
  review_rate: 0.25,
  unknown_rate: 0.25,
  review_queue_size: 2,
  no_review_needed_count: 2,
  automation_rate: 0.5,
  last_reclassification: null,
  pass_history: [],
  detection_coverage: {
    scanned_count: 120,
    processed_count: 100,
    with_crops_count: 30,
    without_crops_count: 70,
    awaiting_detection_count: 15,
    unprocessable_count: 5,
    with_crops_rate: 0.3,
  },
};

vi.mock("../../lib/api", () => ({
  getLearningMetrics: vi.fn(() => Promise.resolve(metrics)),
  getDogs: vi.fn(() => Promise.resolve([])),
}));

describe("MetricsPage library coverage", () => {
  it("states the denominator next to the coverage figure", async () => {
    render(<MetricsPage />);

    expect(await screen.findByText("Photos with a pet crop")).toBeInTheDocument();
    expect(screen.getByText("30%")).toBeInTheDocument();
    expect(
      screen.getByText("30 of 100 photos detection has finished with"),
    ).toBeInTheDocument();
  });

  it("shows photos that produced no crop as their own count", async () => {
    render(<MetricsPage />);

    expect(await screen.findByText("Photos with no pet crop")).toBeInTheDocument();
    expect(screen.getByText("70")).toBeInTheDocument();
  });

  it("does not describe coverage as accuracy or recall", async () => {
    render(<MetricsPage />);

    const description = await screen.findByText(/This is coverage, not accuracy or recall/);

    expect(description).toBeInTheDocument();
  });

  it("keeps the automation rate measured over classified crops", async () => {
    render(<MetricsPage />);

    expect(
      await screen.findByText(
        /2 of 4 images require no manual review right now/,
      ),
    ).toBeInTheDocument();
  });
});
