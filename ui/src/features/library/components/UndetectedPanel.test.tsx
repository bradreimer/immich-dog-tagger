import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { UndetectedPanel } from "./UndetectedPanel";
import * as api from "@/lib/api";
import type { Dog } from "@/types/dogs";

vi.mock("@/lib/api", () => ({
  getUndetectedAssets: vi.fn(),
  tagUndetectedAsset: vi.fn(),
  untagUndetectedAsset: vi.fn(),
  getSettings: vi.fn(),
}));

const IDENTITIES: Dog[] = [
  { id: 1, name: "Fibs", species: "dog", active: true },
  { id: 2, name: "Whiskers", species: "cat", active: true },
];

function buildPage(overrides = {}) {
  return {
    items: [
      {
        asset_id: 7,
        immich_asset_id: "immich-7",
        captured_at: "2026-01-05T12:00:00Z",
        identities: [],
      },
    ],
    total: 1,
    limit: 12,
    offset: 0,
    ...overrides,
  };
}

describe("UndetectedPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.getSettings).mockResolvedValue({
      immich_url: "http://immich.local:2283",
      immich_external_url: "http://immich.local:2283",
    } as never);
  });

  it("lists photos the detector found nothing in", async () => {
    vi.mocked(api.getUndetectedAssets).mockResolvedValue(buildPage());

    render(<UndetectedPanel identities={IDENTITIES} />);

    expect(await screen.findByText(/Taken/)).toBeInTheDocument();
    expect(screen.getByText("1-1 of 1")).toBeInTheDocument();

    // There is no crop, so the only way to see the photo is in Immich.
    expect(screen.getByRole("link", { name: /View in Immich/ })).toBeInTheDocument();
  });

  it("tags a photo with a pet", async () => {
    vi.mocked(api.getUndetectedAssets).mockResolvedValue(buildPage());
    vi.mocked(api.tagUndetectedAsset).mockResolvedValue({
      asset_id: 7,
      identities: ["Fibs"],
    });

    render(<UndetectedPanel identities={IDENTITIES} />);

    const chooser = await screen.findByRole("combobox");

    fireEvent.change(chooser, { target: { value: "1" } });

    await waitFor(() => {
      expect(api.tagUndetectedAsset).toHaveBeenCalledWith(7, "Fibs", "dog");
    });

    expect(await screen.findByText("Fibs")).toBeInTheDocument();
  });

  it("removes a tag that was applied by mistake", async () => {
    vi.mocked(api.getUndetectedAssets).mockResolvedValue(
      buildPage({
        items: [
          {
            asset_id: 7,
            immich_asset_id: "immich-7",
            captured_at: "2026-01-05T12:00:00Z",
            identities: ["Fibs"],
          },
        ],
      }),
    );
    vi.mocked(api.untagUndetectedAsset).mockResolvedValue({
      asset_id: 7,
      identities: [],
    });

    render(<UndetectedPanel identities={IDENTITIES} />);

    fireEvent.click(
      await screen.findByRole("button", { name: "Remove Fibs from this photo" }),
    );

    await waitFor(() => {
      expect(api.untagUndetectedAsset).toHaveBeenCalledWith(7, "Fibs", "dog");
    });
  });

  it("defaults to the photos not yet tagged", async () => {
    vi.mocked(api.getUndetectedAssets).mockResolvedValue(buildPage());

    render(<UndetectedPanel identities={IDENTITIES} />);

    await waitFor(() => {
      expect(api.getUndetectedAssets).toHaveBeenCalledWith({
        limit: 12,
        offset: 0,
        tagged: false,
      });
    });
  });

  it("says so when nothing is left to rescue", async () => {
    vi.mocked(api.getUndetectedAssets).mockResolvedValue(
      buildPage({ items: [], total: 0 }),
    );

    render(<UndetectedPanel identities={IDENTITIES} />);

    expect(
      await screen.findByText(
        "Nothing here — every photo the detector missed has been tagged.",
      ),
    ).toBeInTheDocument();
  });
});
