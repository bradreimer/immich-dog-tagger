// Reuses the app's existing validated categorical chart palette (blue/amber)
// to make Dog and Cat visually distinguishable from each other and from the
// single-accent-color identity/action buttons -- not a new color invented
// for this feature (ux-principles.md #2/#20). Shared by any species control
// (Review's full SpeciesChooser card, Photo Lookup's compact per-detection
// row) so they stay visually consistent.
export const SPECIES_STYLES: Record<"dog" | "cat", string> = {
  dog: "border-chart-1/45 bg-chart-1/12 text-chart-1 hover:bg-chart-1/20",
  cat: "border-chart-4/45 bg-chart-4/12 text-chart-4 hover:bg-chart-4/20",
};
