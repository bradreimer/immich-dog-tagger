import { useCallback, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

import { getDogs } from "@/lib/api";
import type { Dog } from "@/types/dogs";
import { LibraryWorkspaceContext } from "./libraryWorkspace";
import type { LibraryWorkspace, SpeciesSelection } from "./libraryWorkspace";

interface Props {
  children: ReactNode;
}

export function LibraryWorkspaceProvider({ children }: Props) {
  const [identities, setIdentities] = useState<Dog[]>([]);
  const [loadingIdentities, setLoadingIdentities] = useState(true);
  const [identitiesError, setIdentitiesError] = useState<string | null>(null);
  const [species, setSpecies] = useState<SpeciesSelection>("all");
  const [identity, setIdentity] = useState("");
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    let cancelled = false;

    setLoadingIdentities(true);
    setIdentitiesError(null);

    getDogs({ includeInactive: false })
      .then((items) => {
        if (!cancelled) {
          setIdentities(items);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setIdentitiesError(err instanceof Error ? err.message : "Failed to load identities");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoadingIdentities(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [reloadToken]);

  const speciesIdentities = useMemo(
    () => identities.filter((dog) => species === "all" || dog.species === species),
    [identities, species],
  );

  const selectSpecies = useCallback(
    (next: SpeciesSelection) => {
      setSpecies(next);

      // A pet that does not belong to the newly selected species no longer
      // applies -- keeping it would scope the library to an impossible
      // combination (a dog under Cats) and return nothing.
      setIdentity((current) => {
        if (!current || next === "all") {
          return current;
        }

        const pet = identities.find((dog) => dog.name === current);

        return pet && pet.species === next ? current : "";
      });
    },
    [identities],
  );

  const selectIdentity = useCallback((next: string) => {
    setIdentity(next);
  }, []);

  const reloadIdentities = useCallback(() => {
    setReloadToken((current) => current + 1);
  }, []);

  const selectedPet = useMemo(
    () => (identity ? (identities.find((dog) => dog.name === identity) ?? null) : null),
    [identities, identity],
  );

  const value: LibraryWorkspace = useMemo(
    () => ({
      species,
      identity,
      identities,
      speciesIdentities,
      selectedPet,
      loadingIdentities,
      identitiesError,
      selectSpecies,
      selectIdentity,
      reloadIdentities,
    }),
    [
      species,
      identity,
      identities,
      speciesIdentities,
      selectedPet,
      loadingIdentities,
      identitiesError,
      selectSpecies,
      selectIdentity,
      reloadIdentities,
    ],
  );

  return (
    <LibraryWorkspaceContext.Provider value={value}>{children}</LibraryWorkspaceContext.Provider>
  );
}
