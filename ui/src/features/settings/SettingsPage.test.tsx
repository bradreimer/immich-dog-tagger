import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

import { SettingsPage } from "./SettingsPage";
import * as api from "../../lib/api";

vi.mock("../../lib/api", () => ({
  getSettings: vi.fn().mockResolvedValue({
    immich_url: "http://immich-server:2283",
    immich_external_url: "https://immich.example.com",
    scanned_image_count: 42,
    version: "1.6.0",
    tagging_sensitivity: "balanced",
  }),
  setTaggingSensitivity: vi.fn(),
}));

describe("SettingsPage", () => {
  it("shows the running app version", async () => {
    render(<SettingsPage />);

    expect(await screen.findByText("v1.6.0")).toBeInTheDocument();
  });

  it("shows the API URL and the browser-facing link URL separately", async () => {
    render(<SettingsPage />);

    expect(await screen.findByText("http://immich-server:2283")).toBeInTheDocument();
    expect(screen.getByText("https://immich.example.com")).toBeInTheDocument();
  });

  it("re-fetches the version when the settings are refreshed", async () => {
    render(<SettingsPage />);

    await screen.findByText("v1.6.0");

    vi.mocked(api.getSettings).mockResolvedValueOnce({
      immich_url: "http://immich-server:2283",
      immich_external_url: "https://immich.example.com",
      scanned_image_count: 42,
      version: "1.7.0",
      tagging_sensitivity: "balanced",
    });

    screen.getByRole("button", { name: "Refresh" }).click();

    expect(await screen.findByText("v1.7.0")).toBeInTheDocument();
  });

  it("links to buy me a coffee from the about section", async () => {
    render(<SettingsPage />);

    const link = await screen.findByRole("link", {
      name: /Buy Fibs and Hermann a treat/,
    });

    expect(link).toHaveAttribute("href", "https://buymeacoffee.com/bradreimer");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("lets the owner change how cautious automatic tagging is", async () => {
    vi.mocked(api.setTaggingSensitivity).mockResolvedValue({
      immich_url: "http://immich-server:2283",
      immich_external_url: "https://immich.example.com",
      scanned_image_count: 42,
      version: "1.6.0",
      tagging_sensitivity: "cautious",
    });

    render(<SettingsPage />);

    const option = await screen.findByRole("radio", { name: /Ask me more often/ });

    expect(screen.getByRole("radio", { name: /Balanced/ })).toHaveAttribute(
      "aria-checked",
      "true",
    );

    option.click();

    await waitFor(() => {
      expect(api.setTaggingSensitivity).toHaveBeenCalledWith("cautious");
    });

    await waitFor(() => {
      expect(screen.getByRole("radio", { name: /Ask me more often/ })).toHaveAttribute(
        "aria-checked",
        "true",
      );
    });
  });
});
