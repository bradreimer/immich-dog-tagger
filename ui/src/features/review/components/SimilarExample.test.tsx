import { describe, expect, it } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import { SimilarExample } from "./SimilarExample";

describe("SimilarExample", () => {
  it("is collapsed by default and doesn't request the reference image", () => {
    render(
      <SimilarExample
        exampleId={7}
        identity="Rex"
        similarity={0.92}
        capturedAt="2026-01-05T12:00:00Z"
      />,
    );

    expect(screen.getByText("Similar memory")).toBeInTheDocument();
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
  });

  it("loads the reference image only once expanded", () => {
    render(
      <SimilarExample
        exampleId={7}
        identity="Rex"
        similarity={0.92}
        capturedAt="2026-01-05T12:00:00Z"
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /similar memory/i }));

    const img = screen.getByRole("img", { name: /similar example of rex/i });
    expect(img).toHaveAttribute("src", "/api/embedding-examples/7/image");
  });

  it("keeps the image mounted after collapsing again, so it isn't re-requested", () => {
    render(
      <SimilarExample
        exampleId={7}
        identity="Rex"
        similarity={0.92}
        capturedAt="2026-01-05T12:00:00Z"
      />,
    );

    const trigger = screen.getByRole("button", { name: /similar memory/i });

    fireEvent.click(trigger);
    expect(screen.getByRole("img")).toBeInTheDocument();

    // Collapsing hides the panel via the `hidden` attribute rather than
    // unmounting it, so the <img> stays in the DOM and isn't re-requested.
    fireEvent.click(trigger);
    expect(screen.getByRole("img", { hidden: true })).toBeInTheDocument();
  });
});
