import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { DogManagementCard } from "./DogManagementCard";
import * as api from "../../../lib/api";

const dogs = [
  { id: 1, name: "Fibsy", species: "dog" as const, active: true },
  { id: 2, name: "Fibs", species: "dog" as const, active: true },
  { id: 3, name: "Mittens", species: "cat" as const, active: true },
];

vi.mock("../../../lib/api", () => ({
  getDogs: vi.fn(),
  createDog: vi.fn(),
  renameDog: vi.fn(),
  activateDog: vi.fn(),
  deactivateDog: vi.fn(),
  mergeDogs: vi.fn(),
}));

function renderCard() {
  vi.mocked(api.getDogs).mockResolvedValue(dogs);
  return render(<DogManagementCard onNavigate={() => {}} />);
}

describe("DogManagementCard merge", () => {
  it("only offers same-species identities as merge targets", async () => {
    renderCard();

    await screen.findByDisplayValue("Fibsy");

    fireEvent.click(screen.getAllByRole("button", { name: "Merge" })[0]);

    const select = await screen.findByLabelText("Merge into");
    const options = Array.from(select.querySelectorAll("option")).map((option) => option.textContent);

    expect(options).toContain("Fibs");
    expect(options).not.toContain("Mittens");
    expect(options).not.toContain("Fibsy");
  });

  it("cannot merge a species with no other identity of that species", async () => {
    renderCard();

    await screen.findByDisplayValue("Mittens");

    // Mittens is the only cat, so its Merge button has nothing to merge into.
    expect(screen.getAllByRole("button", { name: "Merge" })[2]).toBeDisabled();
  });

  it("confirms before merging and reports what moved", async () => {
    renderCard();

    vi.mocked(api.mergeDogs).mockResolvedValue({
      source: { ...dogs[0], active: false },
      target: dogs[1],
      classifications_reassigned: 12,
      examples_reassigned: 3,
      examples_discarded: 1,
      occurrences_reassigned: 12,
    });

    await screen.findByDisplayValue("Fibsy");

    fireEvent.click(screen.getAllByRole("button", { name: "Merge" })[0]);
    fireEvent.change(await screen.findByLabelText("Merge into"), { target: { value: "2" } });
    fireEvent.click(screen.getAllByRole("button", { name: "Merge" })[1]);

    // Nothing has been sent yet -- the confirmation step comes first.
    expect(api.mergeDogs).not.toHaveBeenCalled();
    expect(await screen.findByText("Merge “Fibsy” into “Fibs”?")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Yes, merge into/ }));

    await waitFor(() => expect(api.mergeDogs).toHaveBeenCalledWith(1, 2));

    expect(
      await screen.findByText(/12 photo\(s\) and 3 reference example\(s\) moved/),
    ).toBeInTheDocument();
    expect(screen.getByText(/Run a sync to update the Immich albums/)).toBeInTheDocument();
  });
});
