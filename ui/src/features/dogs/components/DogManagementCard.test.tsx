import { beforeEach, describe, expect, it, vi } from "vitest";
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

async function openMenuFor(name: string) {
  fireEvent.click(await screen.findByRole("button", { name: `More actions for ${name}` }));
}

describe("DogManagementCard merge", () => {
  it("only offers same-species identities as merge targets", async () => {
    renderCard();

    await screen.findByDisplayValue("Fibsy");
    await openMenuFor("Fibsy");
    fireEvent.click(await screen.findByRole("menuitem", { name: "Merge" }));

    const select = await screen.findByLabelText("Merge into");
    const options = Array.from(select.querySelectorAll("option")).map((option) => option.textContent);

    expect(options).toContain("Fibs");
    expect(options).not.toContain("Mittens");
    expect(options).not.toContain("Fibsy");
  });

  it("cannot merge a species with no other identity of that species", async () => {
    renderCard();

    await screen.findByDisplayValue("Mittens");
    await openMenuFor("Mittens");

    // Mittens is the only cat, so clicking its Merge item does nothing.
    fireEvent.click(await screen.findByRole("menuitem", { name: "Merge" }));
    expect(screen.queryByLabelText("Merge into")).not.toBeInTheDocument();
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
    await openMenuFor("Fibsy");
    fireEvent.click(await screen.findByRole("menuitem", { name: "Merge" }));
    fireEvent.change(await screen.findByLabelText("Merge into"), { target: { value: "2" } });
    fireEvent.click(screen.getByRole("button", { name: "Merge" }));

    // Nothing has been sent yet -- the confirmation step comes first.
    expect(api.mergeDogs).not.toHaveBeenCalled();
    expect(await screen.findByText("Merge “Fibsy” into “Fibs”?")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Yes, merge into/ }));

    await waitFor(() => expect(api.mergeDogs).toHaveBeenCalledWith(1, 2));

    expect(
      await screen.findByText(/12 photo\(s\) and 3 reference example\(s\) moved/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Run a sync to update the Immich albums and tags/),
    ).toBeInTheDocument();
  });
});

describe("DogManagementCard row actions", () => {
  it("navigates to Insights, reachable in one click with no overflow menu involved", async () => {
    const onNavigate = vi.fn();
    vi.mocked(api.getDogs).mockResolvedValue(dogs);
    render(<DogManagementCard onNavigate={onNavigate} />);

    await screen.findByDisplayValue("Fibsy");

    const insightsButton = screen.getAllByRole("button", { name: "Insights" })[0];
    fireEvent.click(insightsButton);
    expect(onNavigate).toHaveBeenCalledWith("/dogs/1/insights");

    // Merge lives behind the overflow menu, not inline next to Insights.
    expect(screen.queryByRole("menuitem", { name: "Merge" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Merge" })).not.toBeInTheDocument();
  });

  it("shows a visible unsaved-changes indicator and saves on Enter", async () => {
    vi.mocked(api.getDogs).mockResolvedValue(dogs);
    vi.mocked(api.renameDog).mockResolvedValue({ ...dogs[0], name: "Fibsy II" });
    render(<DogManagementCard onNavigate={() => {}} />);

    const input = await screen.findByDisplayValue("Fibsy");

    expect(screen.queryByText("Unsaved changes")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save name for Fibsy" })).toBeDisabled();

    fireEvent.change(input, { target: { value: "Fibsy II" } });

    expect(screen.getByText("Unsaved changes")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save name for Fibsy" })).toBeEnabled();

    fireEvent.keyDown(input, { key: "Enter" });

    await waitFor(() => expect(api.renameDog).toHaveBeenCalledWith(1, "Fibsy II"));
  });
});

describe("DogManagementCard deactivate", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("does not use destructive styling for Deactivate", async () => {
    vi.mocked(api.getDogs).mockResolvedValue(dogs);
    render(<DogManagementCard onNavigate={() => {}} />);

    await screen.findByDisplayValue("Fibsy");
    await openMenuFor("Fibsy");

    const deactivateItem = await screen.findByRole("menuitem", { name: "Deactivate" });
    expect(deactivateItem.className).not.toContain("bg-destructive");
  });

  it("requires a confirm click before deactivating", async () => {
    vi.mocked(api.getDogs).mockResolvedValue(dogs);
    vi.mocked(api.deactivateDog).mockResolvedValue({ ...dogs[0], active: false });
    render(<DogManagementCard onNavigate={() => {}} />);

    await screen.findByDisplayValue("Fibsy");
    await openMenuFor("Fibsy");
    fireEvent.click(await screen.findByRole("menuitem", { name: "Deactivate" }));

    expect(api.deactivateDog).not.toHaveBeenCalled();

    fireEvent.click(await screen.findByRole("button", { name: "Yes, deactivate" }));

    await waitFor(() => expect(api.deactivateDog).toHaveBeenCalledWith(1));
  });

  it("cancels back without deactivating", async () => {
    vi.mocked(api.getDogs).mockResolvedValue(dogs);
    render(<DogManagementCard onNavigate={() => {}} />);

    await screen.findByDisplayValue("Fibsy");
    await openMenuFor("Fibsy");
    fireEvent.click(await screen.findByRole("menuitem", { name: "Deactivate" }));

    fireEvent.click(await screen.findByRole("button", { name: "Cancel" }));

    expect(screen.queryByRole("button", { name: "Yes, deactivate" })).not.toBeInTheDocument();
    expect(api.deactivateDog).not.toHaveBeenCalled();
  });

  it("activates in a single click, with no confirm step", async () => {
    const inactiveDogs = [{ ...dogs[0], active: false }, dogs[1], dogs[2]];
    vi.mocked(api.getDogs).mockResolvedValue(inactiveDogs);
    vi.mocked(api.activateDog).mockResolvedValue({ ...dogs[0], active: true });
    render(<DogManagementCard onNavigate={() => {}} />);

    await screen.findByDisplayValue("Fibsy");
    await openMenuFor("Fibsy");
    fireEvent.click(await screen.findByRole("menuitem", { name: "Activate" }));

    await waitFor(() => expect(api.activateDog).toHaveBeenCalledWith(1));
  });
});
