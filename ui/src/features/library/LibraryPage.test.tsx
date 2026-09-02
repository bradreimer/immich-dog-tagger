import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { LibraryPage } from "./LibraryPage";
import * as api from "@/lib/api";
import type { Dog } from "@/types/dogs";
import type { LibraryEntry } from "@/types/library";

vi.mock("@/lib/api", () => ({
  getLibrary: vi.fn(),
  getDogs: vi.fn(),
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
      location: "Portland, Oregon, USA",
      not_animal: false,
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
  const items = Array.from({ length: Math.min(total, 50) }, (_, index) => buildEntry(index + 1));

  vi.mocked(api.getLibrary).mockImplementation(async (query = {}) =>
    Promise.resolve({
      items,
      total,
      limit: query.limit ?? 50,
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
    vi.mocked(api.getSettings).mockResolvedValue({
      immich_url: "http://immich.local",
      immich_external_url: "http://immich.local",
      scanned_image_count: 0,
      version: "1.11.0",
      tagging_sensitivity: "balanced",
    });
    mockLibrary(0);
  });

  it("filters by species, pet, review status, and capture date -- combined", async () => {
    render(<LibraryPage />);

    await waitFor(() => expect(api.getLibrary).toHaveBeenCalled());

    fireEvent.change(screen.getByLabelText("Species"), { target: { value: "dog" } });
    await waitFor(() => expect(lastLibraryQuery()).toMatchObject({ species: "dog" }));

    fireEvent.change(screen.getByLabelText("Pet"), { target: { value: "Hermann" } });
    await waitFor(() =>
      expect(lastLibraryQuery()).toMatchObject({ species: "dog", identity: "Hermann" }),
    );

    fireEvent.change(screen.getByLabelText("Review status"), {
      target: { value: "unreviewed" },
    });
    await waitFor(() =>
      expect(lastLibraryQuery()).toMatchObject({
        species: "dog",
        identity: "Hermann",
        reviewed: false,
      }),
    );

    fireEvent.change(screen.getByLabelText("Captured after"), {
      target: { value: "2026-01-01" },
    });
    fireEvent.change(screen.getByLabelText("Captured before"), {
      target: { value: "2026-01-31" },
    });

    await waitFor(() =>
      expect(lastLibraryQuery()).toMatchObject({
        species: "dog",
        identity: "Hermann",
        reviewed: false,
        captured_after: "2026-01-01T00:00:00",
        captured_before: "2026-01-31T23:59:59",
      }),
    );
  });

  it("clears a pet selection that no longer matches a changed species", async () => {
    render(<LibraryPage />);

    fireEvent.change(await screen.findByLabelText("Pet"), {
      target: { value: "Hermann" },
    });

    await waitFor(() => expect(lastLibraryQuery().identity).toBe("Hermann"));

    fireEvent.change(screen.getByLabelText("Species"), { target: { value: "cat" } });

    await waitFor(() => expect(lastLibraryQuery().identity).toBeUndefined());
    expect(screen.getByLabelText("Pet")).toHaveValue("");
  });

  it("sends the selected sort order", async () => {
    render(<LibraryPage />);

    await waitFor(() => expect(lastLibraryQuery().sort).toBe("captured_desc"));

    fireEvent.change(await screen.findByLabelText("Sort"), {
      target: { value: "confidence_desc" },
    });

    await waitFor(() => expect(lastLibraryQuery().sort).toBe("confidence_desc"));
  });

  it("sends the reviewed-date sort order (issue #225)", async () => {
    render(<LibraryPage />);

    await waitFor(() => expect(lastLibraryQuery().sort).toBe("captured_desc"));

    fireEvent.change(await screen.findByLabelText("Sort"), {
      target: { value: "reviewed_desc" },
    });

    await waitFor(() => expect(lastLibraryQuery().sort).toBe("reviewed_desc"));

    fireEvent.change(screen.getByLabelText("Sort"), {
      target: { value: "reviewed_asc" },
    });

    await waitFor(() => expect(lastLibraryQuery().sort).toBe("reviewed_asc"));
  });

  it("resets pagination when a filter or the sort changes", async () => {
    mockLibrary(120);

    render(<LibraryPage />);

    fireEvent.click(await screen.findByRole("button", { name: "Next" }));

    await waitFor(() => expect(lastLibraryQuery().offset).toBe(50));

    fireEvent.change(screen.getByLabelText("Review status"), {
      target: { value: "reviewed" },
    });

    await waitFor(() =>
      expect(lastLibraryQuery()).toMatchObject({ reviewed: true, offset: 0 }),
    );
  });

  it("never renders a photos-with-no-detected-pet section", async () => {
    render(<LibraryPage />);

    await waitFor(() => expect(api.getLibrary).toHaveBeenCalled());

    expect(
      screen.queryByRole("region", { name: "Photos with no detected pet" }),
    ).not.toBeInTheDocument();
  });

  it("shows a details panel when a thumbnail is selected", async () => {
    mockLibrary(1);

    render(<LibraryPage />);

    fireEvent.click(await screen.findByRole("button", { name: "View details for Hermann" }));

    expect(await screen.findByText("Portland, Oregon, USA")).toBeInTheDocument();
    expect(screen.getByText("90.0%")).toBeInTheDocument();
  });

  it("clears the selection when a filter changes", async () => {
    mockLibrary(1);

    render(<LibraryPage />);

    fireEvent.click(await screen.findByRole("button", { name: "View details for Hermann" }));
    expect(await screen.findByText("Portland, Oregon, USA")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Review status"), {
      target: { value: "unreviewed" },
    });

    await waitFor(() =>
      expect(screen.queryByText("Portland, Oregon, USA")).not.toBeInTheDocument(),
    );
  });
});
