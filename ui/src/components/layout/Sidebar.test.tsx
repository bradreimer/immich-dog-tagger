import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

import { Sidebar } from "./Sidebar";
import * as api from "../../lib/api";

vi.mock("../../lib/api", () => ({
  getReviewStats: vi.fn().mockResolvedValue({ remaining: 0 }),
  getHealth: vi.fn().mockResolvedValue({ status: "ok", version: "1.6.0" }),
}));

describe("Sidebar", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("shows the running app version in the footer", async () => {
    render(<Sidebar currentPath="/" onNavigate={vi.fn()} />);

    expect(await screen.findByText("v1.6.0")).toBeInTheDocument();
  });

  it("omits the version when it fails to load", async () => {
    vi.mocked(api.getHealth).mockRejectedValueOnce(new Error("network error"));

    render(<Sidebar currentPath="/" onNavigate={vi.fn()} />);

    await waitFor(() => expect(api.getHealth).toHaveBeenCalled());
    expect(screen.queryByText(/^v\d/)).not.toBeInTheDocument();
  });

  it("highlights Dogs & Cats while on a pet's Insights sub-route", async () => {
    render(<Sidebar currentPath="/dogs/3/insights" onNavigate={vi.fn()} />);

    const link = await screen.findByRole("button", { name: "Dogs & Cats" });
    expect(link).toHaveAttribute("aria-current", "page");
  });

  it("only highlights Overview on the exact root path", async () => {
    render(<Sidebar currentPath="/photo-lookup" onNavigate={vi.fn()} />);

    const overviewLink = await screen.findByRole("button", { name: "Overview" });
    expect(overviewLink).not.toHaveAttribute("aria-current", "page");

    const photoLookupLink = screen.getByRole("button", { name: "Photo Lookup" });
    expect(photoLookupLink).toHaveAttribute("aria-current", "page");
  });
});
