import { createContext, useContext } from "react";

import type { Dog } from "@/types/dogs";

/** "all" browses both species; "dog"/"cat" scope the workspace to one of them. */
export type SpeciesSelection = "all" | "dog" | "cat";

/**
 * The Library's selection state: which species, and which pet within it.
 *
 * This lives in a context rather than in the filter row because the selected pet
 * is the primary axis of the workspace -- everything the Library shows or acts on
 * is scoped to it, and surfaces beyond the flat grid read the same selection.
 */
export interface LibraryWorkspace {
  species: SpeciesSelection;
  /** Empty string means "all photos" for the selected species. */
  identity: string;
  /** Active identities, both species. */
  identities: Dog[];
  /** Active identities that match the selected species. */
  speciesIdentities: Dog[];
  /** The selected pet, or null when browsing all photos. */
  selectedPet: Dog | null;
  loadingIdentities: boolean;
  identitiesError: string | null;
  selectSpecies: (species: SpeciesSelection) => void;
  selectIdentity: (identity: string) => void;
  reloadIdentities: () => void;
}

export const LibraryWorkspaceContext = createContext<LibraryWorkspace | null>(null);

export function useLibraryWorkspace(): LibraryWorkspace {
  const workspace = useContext(LibraryWorkspaceContext);

  if (!workspace) {
    throw new Error("useLibraryWorkspace must be used inside a LibraryWorkspaceProvider");
  }

  return workspace;
}
