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
  getSchedules: vi.fn().mockResolvedValue([]),
  createSchedule: vi.fn(),
  updateSchedule: vi.fn(),
  runScheduleNow: vi.fn(),
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

  it("mounts the buy me a coffee widget only while settings is shown", async () => {
    const { unmount } = render(<SettingsPage />);

    await screen.findByText("v1.6.0");

    const script = document.querySelector<HTMLScriptElement>(
      'script[data-name="BMC-Widget"]',
    );

    expect(script).not.toBeNull();
    expect(script).toHaveAttribute("data-id", "bradreimer");
    expect(script).toHaveAttribute(
      "data-message",
      "Thank you for visiting. Buy Fibs and Hermann a treat.",
    );

    unmount();

    expect(document.querySelector('script[data-name="BMC-Widget"]')).toBeNull();
  });

  it("redispatches DOMContentLoaded once the widget script loads, so it actually renders in an SPA", async () => {
    render(<SettingsPage />);

    await screen.findByText("v1.6.0");

    const script = document.querySelector<HTMLScriptElement>(
      'script[data-name="BMC-Widget"]',
    );
    const onDomContentLoaded = vi.fn();
    document.addEventListener("DOMContentLoaded", onDomContentLoaded);

    script?.onload?.(new Event("load"));

    expect(onDomContentLoaded).toHaveBeenCalledTimes(1);

    document.removeEventListener("DOMContentLoaded", onDomContentLoaded);
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
