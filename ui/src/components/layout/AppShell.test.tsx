import { describe, expect, it, vi } from "vitest";
import { render } from "@testing-library/react";

import { AppShell } from "./AppShell";

vi.mock("@/lib/api", () => ({
  getHealth: vi.fn().mockRejectedValue(new Error("not mocked")),
  getReviewStats: vi.fn().mockRejectedValue(new Error("not mocked")),
}));

describe("AppShell", () => {
  it("clips horizontal overflow on `main` without implying an overflow-y scroll container", () => {
    const { container } = render(
      <AppShell currentPath="/library" onNavigate={() => {}}>
        <div>content</div>
      </AppShell>,
    );

    const main = container.querySelector("main");

    // overflow-x-hidden (rather than -clip) leaves overflow-y unset, which the
    // browser then computes to "auto" -- silently turning `main` into a
    // scroll container that breaks `position: sticky` for any descendant
    // (e.g. the Library page's details panel) even though `main` itself
    // never actually scrolls. See AppShell.tsx for the fuller explanation.
    expect(main).toHaveClass("overflow-x-clip");
    expect(main).not.toHaveClass("overflow-x-hidden");
  });
});
