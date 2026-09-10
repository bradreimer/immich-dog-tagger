import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import { MetricsPage } from "./MetricsPage";
import { getDogs, getSpeciesTimeline } from "../../lib/api";
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
    with_dog_count: 30,
    with_dog_rate: 0.3,
    with_cat_count: 12,
    with_cat_rate: 0.12,
    awaiting_detection_count: 15,
    unprocessable_count: 5,
  },
};

vi.mock("../../lib/api", () => ({
  getLearningMetrics: vi.fn(() => Promise.resolve(metrics)),
  getDogs: vi.fn(() => Promise.resolve([])),
  getSpeciesTimeline: vi.fn(() => Promise.resolve({ species: "dog", identities: [], points: [] })),
}));

describe("MetricsPage library coverage", () => {
  it("states the denominator next to the dog coverage figure", async () => {
    render(<MetricsPage onNavigate={vi.fn()} />);

    expect(await screen.findByText("Photos with a dog")).toBeInTheDocument();
    expect(screen.getByText("30%")).toBeInTheDocument();
    expect(
      screen.getByText("30 of 100 photos detection has finished with"),
    ).toBeInTheDocument();
  });

  it("states the denominator next to the cat coverage figure", async () => {
    render(<MetricsPage onNavigate={vi.fn()} />);

    expect(await screen.findByText("Photos with a cat")).toBeInTheDocument();
    expect(screen.getByText("12%")).toBeInTheDocument();
    expect(
      screen.getByText("12 of 100 photos detection has finished with"),
    ).toBeInTheDocument();
  });

  it("does not describe coverage as accuracy or recall", async () => {
    render(<MetricsPage onNavigate={vi.fn()} />);

    const description = await screen.findByText(/This is coverage, not accuracy or recall/);

    expect(description).toBeInTheDocument();
  });

  it("keeps the automation rate measured over classified crops", async () => {
    render(<MetricsPage onNavigate={vi.fn()} />);

    expect(
      await screen.findByText(
        /2 of 4 images require no manual review right now/,
      ),
    ).toBeInTheDocument();
  });
});

describe("MetricsPage species timeline charts", () => {
  it("shows an empty state when a species has no confirmed photos yet", async () => {
    render(<MetricsPage onNavigate={vi.fn()} />);

    expect(
      await screen.findByText(/No confirmed dog photos yet/),
    ).toBeInTheDocument();
    expect(await screen.findByText(/No confirmed cat photos yet/)).toBeInTheDocument();
  });

  it("renders the chart instead of the empty state once a species has data", async () => {
    vi.mocked(getSpeciesTimeline).mockImplementation((species) =>
      Promise.resolve(
        species === "dog"
          ? {
              species: "dog",
              identities: ["Hermann"],
              points: [{ label: "Fall 2026", counts: { Hermann: 3 } }],
            }
          : { species: "cat", identities: [], points: [] },
      ),
    );

    render(<MetricsPage onNavigate={vi.fn()} />);

    expect(await screen.findByText("Dogs Over Time")).toBeInTheDocument();
    expect(screen.queryByText(/No confirmed dog photos yet/)).not.toBeInTheDocument();
    expect(await screen.findByText(/No confirmed cat photos yet/)).toBeInTheDocument();
  });

  it("navigates to a pet's Insights page from the timeline legend", async () => {
    vi.mocked(getDogs).mockResolvedValueOnce([
      { id: 9, name: "Hermann", species: "dog", active: true },
    ]);
    vi.mocked(getSpeciesTimeline).mockImplementation((species) =>
      Promise.resolve(
        species === "dog"
          ? {
              species: "dog",
              identities: ["Hermann"],
              points: [{ label: "Fall 2026", counts: { Hermann: 3 } }],
            }
          : { species: "cat", identities: [], points: [] },
      ),
    );
    const onNavigate = vi.fn();

    render(<MetricsPage onNavigate={onNavigate} />);

    const navButton = await screen.findByRole("button", {
      name: "Open Hermann's Insights page",
    });
    fireEvent.click(navButton);

    expect(onNavigate).toHaveBeenCalledWith("/dogs/9/insights");
  });
});
