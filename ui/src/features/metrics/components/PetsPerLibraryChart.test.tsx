import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { PetsPerLibraryChart } from "./PetsPerLibraryChart";

describe("PetsPerLibraryChart", () => {
  it("renders one labeled bar per library with a dog and cat legend", () => {
    render(
      <PetsPerLibraryChart
        libraries={[
          { library: "Home", dogs_detected: 3, dogs_identified: 2, cats_detected: 1, cats_identified: 0 },
          { library: "Cabin", dogs_detected: 1, dogs_identified: 1, cats_detected: 2, cats_identified: 1 },
        ]}
      />,
    );

    expect(screen.getByRole("img", { name: "Home: 3 dogs, 1 cats" })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Cabin: 1 dogs, 2 cats" })).toBeInTheDocument();
    expect(screen.getByText("Dogs")).toBeInTheDocument();
    expect(screen.getByText("Cats")).toBeInTheDocument();
  });
});
