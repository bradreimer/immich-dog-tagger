import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { PhotoLookupPage } from "./PhotoLookupPage";
import * as api from "@/lib/api";
import type { Dog } from "@/types/dogs";
import type { PhotoLookupResult } from "@/types/photoLookup";

vi.mock("@/lib/api", () => ({
  getDogs: vi.fn(),
  getPhotoLookup: vi.fn(),
  correctClassification: vi.fn(),
  markCropNotAnimal: vi.fn(),
  unmarkCropNotAnimal: vi.fn(),
  PhotoLookupNotFoundError: class PhotoLookupNotFoundError extends Error {},
}));

const HERMANN: Dog = { id: 1, name: "Hermann", species: "dog", active: true };
const FIBS: Dog = { id: 2, name: "Fibs", species: "dog", active: true };

function buildResult(): PhotoLookupResult {
  return {
    asset_id: 1,
    immich_asset_id: "asset-42",
    captured_at: "2026-01-05T12:00:00Z",
    detections: [
      {
        detection_id: 1,
        x1: 10,
        y1: 20,
        x2: 110,
        y2: 220,
        species: "dog",
        crop_id: 1,
        classification_id: 100,
        identity: "Hermann",
        confidence: 0.87,
        not_animal: false,
      },
    ],
  };
}

async function pasteAndSubmit(url: string) {
  const input = screen.getByPlaceholderText("Paste an Immich photo link");
  fireEvent.change(input, { target: { value: url } });
  fireEvent.click(screen.getByRole("button", { name: /look up/i }));
}

describe("PhotoLookupPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("rejects a URL that isn't an Immich photo link before calling the API", async () => {
    vi.mocked(api.getDogs).mockResolvedValue([]);

    render(<PhotoLookupPage />);

    await pasteAndSubmit("not a url");

    expect(
      await screen.findByText(/Paste a full Immich photo link/i),
    ).toBeInTheDocument();
    expect(api.getPhotoLookup).not.toHaveBeenCalled();
  });

  it("shows a not-found message when the photo hasn't been scanned", async () => {
    vi.mocked(api.getDogs).mockResolvedValue([]);
    vi.mocked(api.getPhotoLookup).mockRejectedValue(
      new api.PhotoLookupNotFoundError("That photo hasn't been scanned by this instance yet."),
    );

    render(<PhotoLookupPage />);

    await pasteAndSubmit("http://immich.local/photos/unknown-asset");

    expect(
      await screen.findByText(/hasn't been scanned by this instance yet/i),
    ).toBeInTheDocument();
  });

  it("renders each detection's predicted identity and confidence", async () => {
    vi.mocked(api.getDogs).mockResolvedValue([HERMANN, FIBS]);
    vi.mocked(api.getPhotoLookup).mockResolvedValue(buildResult());

    render(<PhotoLookupPage />);

    await pasteAndSubmit("http://immich.local/photos/asset-42");

    expect(await screen.findAllByText("Hermann")).not.toHaveLength(0);
    expect(screen.getByText("87.0% confidence")).toBeInTheDocument();
  });

  it("corrects a detection's identity in place", async () => {
    vi.mocked(api.getDogs).mockResolvedValue([HERMANN, FIBS]);
    vi.mocked(api.getPhotoLookup).mockResolvedValue(buildResult());
    vi.mocked(api.correctClassification).mockResolvedValue(undefined);

    render(<PhotoLookupPage />);

    await pasteAndSubmit("http://immich.local/photos/asset-42");

    const select = await screen.findByLabelText("Correct identity for detection 1");
    fireEvent.change(select, { target: { value: "Fibs" } });

    await waitFor(() => {
      expect(api.correctClassification).toHaveBeenCalledWith(100, "Fibs");
    });

    expect(await screen.findAllByText("Fibs")).not.toHaveLength(0);
  });

  it("marks a detection as not a dog or cat, and can undo it", async () => {
    vi.mocked(api.getDogs).mockResolvedValue([HERMANN, FIBS]);
    vi.mocked(api.getPhotoLookup).mockResolvedValue(buildResult());
    vi.mocked(api.markCropNotAnimal).mockResolvedValue(undefined);
    vi.mocked(api.unmarkCropNotAnimal).mockResolvedValue(undefined);

    render(<PhotoLookupPage />);

    await pasteAndSubmit("http://immich.local/photos/asset-42");

    fireEvent.click(await screen.findByRole("button", { name: /not a dog or cat/i }));

    await waitFor(() => {
      expect(api.markCropNotAnimal).toHaveBeenCalledWith(1);
    });

    expect(await screen.findAllByText("Not a dog or cat")).not.toHaveLength(0);

    fireEvent.click(screen.getByRole("button", { name: /undo/i }));

    await waitFor(() => {
      expect(api.unmarkCropNotAnimal).toHaveBeenCalledWith(1);
    });

    expect(await screen.findAllByText("Hermann")).not.toHaveLength(0);
  });

  it("shows a distinct message when no dogs or cats were detected", async () => {
    vi.mocked(api.getDogs).mockResolvedValue([]);
    vi.mocked(api.getPhotoLookup).mockResolvedValue({
      ...buildResult(),
      detections: [],
    });

    render(<PhotoLookupPage />);

    await pasteAndSubmit("http://immich.local/photos/asset-42");

    expect(
      await screen.findByText(/No dogs or cats were detected/i),
    ).toBeInTheDocument();
  });
});
