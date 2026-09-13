import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

import { DogInsightsPage } from "./DogInsightsPage";
import * as api from "../../lib/api";
import type { InsightsSummary, TopPhoto } from "../../types/insights";

vi.mock("../../lib/api", () => ({
  getInsightsCards: vi.fn(),
  getInsightsPeople: vi.fn(),
  getInsightsPlaces: vi.fn(),
  getInsightsSummary: vi.fn(),
  getInsightsTopPhotos: vi.fn(),
}));

function buildSummary(overrides: Partial<InsightsSummary> = {}): InsightsSummary {
  return {
    identity_id: 1,
    identity_name: "Hermann",
    identity_species: "dog",
    total_photos: 1,
    first_seen: "2023-01-01T00:00:00Z",
    last_seen: "2023-01-01T00:00:00Z",
    photos_by_year: { 2023: 1 },
    favorite_photo_count: 0,
    ...overrides,
  };
}

const topPhoto: TopPhoto = {
  asset_id: 1,
  immich_asset_id: "immich-1",
  crop_id: 1,
  captured_at: "2023-01-01T00:00:00Z",
  clarity: 0.9,
};

describe("DogInsightsPage", () => {
  beforeEach(() => {
    vi.mocked(api.getInsightsCards).mockResolvedValue([]);
    vi.mocked(api.getInsightsPeople).mockResolvedValue([]);
    vi.mocked(api.getInsightsPlaces).mockResolvedValue([]);
  });

  it("links Top photos to the pet's filtered Library view", async () => {
    vi.mocked(api.getInsightsSummary).mockResolvedValue(buildSummary());
    vi.mocked(api.getInsightsTopPhotos).mockResolvedValue([topPhoto]);
    const onNavigate = vi.fn();

    render(<DogInsightsPage dogId={1} onNavigate={onNavigate} />);

    const link = await screen.findByRole("button", { name: /continue browsing in library/i });
    link.click();

    expect(onNavigate).toHaveBeenCalledWith("/library?species=dog&identity=Hermann");
  });

  it("does not render the Library link when there are no top photos", async () => {
    vi.mocked(api.getInsightsSummary).mockResolvedValue(buildSummary({ total_photos: 0 }));
    vi.mocked(api.getInsightsTopPhotos).mockResolvedValue([]);

    render(<DogInsightsPage dogId={1} onNavigate={vi.fn()} />);

    await waitFor(() => expect(api.getInsightsSummary).toHaveBeenCalled());

    expect(
      screen.queryByRole("button", { name: /continue browsing in library/i }),
    ).not.toBeInTheDocument();
  });
});
