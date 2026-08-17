import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

import { SettingsPage } from "./SettingsPage";
import * as api from "../../lib/api";

vi.mock("../../lib/api", () => ({
  getSettings: vi.fn().mockResolvedValue({
    immich_url: "http://localhost:2283",
    scanned_image_count: 42,
    version: "1.6.0",
  }),
}));

describe("SettingsPage", () => {
  it("shows the running app version", async () => {
    render(<SettingsPage />);

    expect(await screen.findByText("v1.6.0")).toBeInTheDocument();
  });

  it("re-fetches the version when the settings are refreshed", async () => {
    render(<SettingsPage />);

    await screen.findByText("v1.6.0");

    vi.mocked(api.getSettings).mockResolvedValueOnce({
      immich_url: "http://localhost:2283",
      scanned_image_count: 42,
      version: "1.7.0",
    });

    screen.getByRole("button", { name: "Refresh" }).click();

    expect(await screen.findByText("v1.7.0")).toBeInTheDocument();
  });
});
