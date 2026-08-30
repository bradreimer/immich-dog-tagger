import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { LibraryPage } from "./LibraryPage";
import * as api from "@/lib/api";
import type { Dog } from "@/types/dogs";
import type { LibraryEntry } from "@/types/library";

vi.mock("@/lib/api", () => ({
  getLibrary: vi.fn(),
  getDogs: vi.fn(),
  correctClassification: vi.fn(),
  getPetClusters: vi.fn(),
  approveCluster: vi.fn(),
  getConfirmedClusters: vi.fn(),
  moveConfirmedPhotos: vi.fn(),
  getUndetectedAssets: vi.fn(),
  getSettings: vi.fn(),
}));

const HERMANN: Dog = { id: 1, name: "Hermann", species: "dog", active: true };
const MINA: Dog = { id: 2, name: "Mina", species: "cat", active: true };

function buildEntry(classificationId: number): LibraryEntry {
  return {
    reviewed: false,
    reviewed_at: null,
    item: {
      classification_id: classificationId,
      crop_id: classificationId,
      path: `/photos/${classificationId}.jpg`,
      filename: `${classificationId}.jpg`,
      species: "dog",
      reason: "review",
      captured_at: "2026-01-05T12:00:00Z",
      immich_asset_id: `asset-${classificationId}`,
      prediction: {
        identity: "Hermann",
        similarity: 0.9,
        candidates: [],
      },
      suggestion: null,
    },
  };
}

function mockLibrary(total: number) {
  const items = Array.from({ length: Math.min(total, 24) }, (_, index) => buildEntry(index + 1));

  vi.mocked(api.getLibrary).mockImplementation(async (query = {}) =>
    Promise.resolve({
      items,
      total,
      limit: query.limit ?? 24,
      offset: query.offset ?? 0,
    }),
  );
}

function lastLibraryQuery() {
  const calls = vi.mocked(api.getLibrary).mock.calls;

  return calls[calls.length - 1]?.[0] ?? {};
}

describe("LibraryPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.getDogs).mockResolvedValue([HERMANN, MINA]);
    vi.mocked(api.getPetClusters).mockResolvedValue({
      identity: "Hermann",
      species: "dog",
      clusters: [],
      excluded: [],
      candidate_count: 0,
      clustered_count: 0,
      distance_threshold: 0.2,
      truncated: false,
      sort: "confidence_desc",
    });
    vi.mocked(api.getConfirmedClusters).mockResolvedValue({
      identity: "Hermann",
      species: "dog",
      clusters: [],
      excluded: [],
      candidate_count: 0,
      clustered_count: 0,
      distance_threshold: 0.2,
      truncated: false,
      sort: "confidence_desc",
    });
    mockLibrary(0);
    vi.mocked(api.getUndetectedAssets).mockResolvedValue({
      items: [],
      total: 0,
      limit: 12,
      offset: 0,
    });
    vi.mocked(api.getSettings).mockResolvedValue({
      immich_url: "http://immich.local",
      immich_external_url: "http://immich.local",
      scanned_image_count: 0,
      version: "0.0.0",
      tagging_sensitivity: "balanced",
    });
  });

  it("scopes the library to the selected pet", async () => {
    render(<LibraryPage onNavigate={vi.fn()} />);

    fireEvent.click(await screen.findByRole("button", { name: "Hermann" }));

    await waitFor(() => {
      expect(lastLibraryQuery().identity).toBe("Hermann");
    });

    expect(
      screen.getByText("Every photo classified as Hermann, reviewed and unreviewed alike."),
    ).toBeInTheDocument();
  });

  it("offers cluster recommendations for the selected pet only", async () => {
    render(<LibraryPage onNavigate={vi.fn()} />);

    await screen.findByRole("button", { name: "All photos" });

    expect(
      screen.queryByRole("region", { name: "Recommendations for Hermann" }),
    ).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Hermann" }));

    expect(
      await screen.findByRole("region", { name: "Recommendations for Hermann" }),
    ).toBeInTheDocument();

    await waitFor(() => {
      expect(api.getPetClusters).toHaveBeenCalledWith(
        "Hermann",
        "dog",
        "confidence_desc",
      );
    });
  });

  it("clears a pet selection that no longer applies when the species changes", async () => {
    render(<LibraryPage onNavigate={vi.fn()} />);

    fireEvent.click(await screen.findByRole("button", { name: "Hermann" }));

    await waitFor(() => {
      expect(lastLibraryQuery().identity).toBe("Hermann");
    });

    fireEvent.click(screen.getByRole("button", { name: "Cats" }));

    await waitFor(() => {
      expect(lastLibraryQuery()).toMatchObject({ species: "cat" });
    });

    expect(lastLibraryQuery().identity).toBeUndefined();
    expect(screen.queryByRole("button", { name: "Hermann" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Mina" })).toBeInTheDocument();
  });

  it("keeps a pet selection that still applies under the new species", async () => {
    render(<LibraryPage onNavigate={vi.fn()} />);

    fireEvent.click(await screen.findByRole("button", { name: "Hermann" }));
    fireEvent.click(screen.getByRole("button", { name: "Dogs" }));

    await waitFor(() => {
      expect(lastLibraryQuery()).toMatchObject({ species: "dog", identity: "Hermann" });
    });
  });

  it("resets pagination when the selection changes", async () => {
    mockLibrary(50);

    render(<LibraryPage onNavigate={vi.fn()} />);

    fireEvent.click(await screen.findByRole("button", { name: "Next" }));

    await waitFor(() => {
      expect(lastLibraryQuery().offset).toBe(24);
    });

    fireEvent.click(screen.getByRole("button", { name: "Hermann" }));

    await waitFor(() => {
      expect(lastLibraryQuery()).toMatchObject({ identity: "Hermann", offset: 0 });
    });
  });

  it("keeps the flat all-photos view and its filters working", async () => {
    mockLibrary(50);

    render(<LibraryPage onNavigate={vi.fn()} />);

    await screen.findByRole("button", { name: "All photos" });

    fireEvent.click(screen.getByRole("button", { name: "Unreviewed" }));

    await waitFor(() => {
      expect(lastLibraryQuery()).toMatchObject({ reviewed: false, offset: 0 });
    });

    expect(lastLibraryQuery().identity).toBeUndefined();
    expect(lastLibraryQuery().species).toBeUndefined();

    fireEvent.click(screen.getByRole("button", { name: "Next" }));

    await waitFor(() => {
      expect(lastLibraryQuery().offset).toBe(24);
    });
  });

  it("shows the missed-detection rescue panel only when no pet is selected", async () => {
    render(<LibraryPage onNavigate={vi.fn()} />);

    expect(
      await screen.findByRole("region", { name: "Photos with no detected pet" }),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Hermann" }));

    await waitFor(() => {
      expect(
        screen.queryByRole("region", { name: "Photos with no detected pet" }),
      ).not.toBeInTheDocument();
    });
  });

  it("points at Dogs & Cats when no identities are configured", async () => {
    vi.mocked(api.getDogs).mockResolvedValue([]);
    const onNavigate = vi.fn();

    render(<LibraryPage onNavigate={onNavigate} />);

    expect(
      await screen.findByText(
        "No dogs or cats configured yet -- add one to browse the library one pet at a time.",
      ),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Go to Dogs & Cats" }));

    expect(onNavigate).toHaveBeenCalledWith("/dogs");
  });
});
