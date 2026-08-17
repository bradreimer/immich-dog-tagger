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
});
