import type { LibrarySort } from "@/types/library";
import type { LibraryReviewedFilter, LibrarySpeciesFilter } from "./components/LibraryFilters";

export interface LibraryUrlState {
  species: LibrarySpeciesFilter;
  identity: string;
  reviewedFilter: LibraryReviewedFilter;
  capturedAfter: string;
  capturedBefore: string;
  sort: LibrarySort;
  offset: number;
}

const DEFAULTS: LibraryUrlState = {
  species: "all",
  identity: "",
  reviewedFilter: "all",
  capturedAfter: "",
  capturedBefore: "",
  sort: "captured_desc",
  offset: 0,
};

const SPECIES_VALUES: LibrarySpeciesFilter[] = ["all", "dog", "cat"];
const REVIEWED_VALUES: LibraryReviewedFilter[] = ["all", "reviewed", "unreviewed"];
const SORT_VALUES: LibrarySort[] = [
  "captured_asc",
  "captured_desc",
  "confidence_desc",
  "confidence_asc",
  "reviewed_desc",
  "reviewed_asc",
];

function pick<T extends string>(value: string | null, allowed: T[], fallback: T): T {
  return allowed.includes(value as T) ? (value as T) : fallback;
}

/** Reads Library filter/sort/pagination state from a `location.search` string. */
export function parseLibraryUrlState(search: string): LibraryUrlState {
  const params = new URLSearchParams(search);

  const offsetParam = Number.parseInt(params.get("offset") ?? "", 10);

  return {
    species: pick(params.get("species"), SPECIES_VALUES, DEFAULTS.species),
    identity: params.get("identity") ?? DEFAULTS.identity,
    reviewedFilter: pick(params.get("reviewed"), REVIEWED_VALUES, DEFAULTS.reviewedFilter),
    capturedAfter: params.get("capturedAfter") ?? DEFAULTS.capturedAfter,
    capturedBefore: params.get("capturedBefore") ?? DEFAULTS.capturedBefore,
    sort: pick(params.get("sort"), SORT_VALUES, DEFAULTS.sort),
    offset: Number.isInteger(offsetParam) && offsetParam > 0 ? offsetParam : DEFAULTS.offset,
  };
}

/**
 * Writes Library filter/sort/pagination state to the URL via `replaceState`,
 * omitting values at their default so the URL stays minimal.
 */
export function writeLibraryUrlState(state: LibraryUrlState): void {
  const params = new URLSearchParams();

  if (state.species !== DEFAULTS.species) {
    params.set("species", state.species);
  }
  if (state.identity !== DEFAULTS.identity) {
    params.set("identity", state.identity);
  }
  if (state.reviewedFilter !== DEFAULTS.reviewedFilter) {
    params.set("reviewed", state.reviewedFilter);
  }
  if (state.capturedAfter !== DEFAULTS.capturedAfter) {
    params.set("capturedAfter", state.capturedAfter);
  }
  if (state.capturedBefore !== DEFAULTS.capturedBefore) {
    params.set("capturedBefore", state.capturedBefore);
  }
  if (state.sort !== DEFAULTS.sort) {
    params.set("sort", state.sort);
  }
  if (state.offset !== DEFAULTS.offset) {
    params.set("offset", String(state.offset));
  }

  const query = params.toString();
  const url = query
    ? `${window.location.pathname}?${query}`
    : window.location.pathname;

  window.history.replaceState({}, "", url);
}
