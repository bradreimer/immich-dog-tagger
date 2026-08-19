import { IconCat, IconDog, IconPaw, IconRefresh } from "@tabler/icons-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import type { Species } from "@/types/dogs";
import { useLibraryWorkspace } from "../libraryWorkspace";
import type { SpeciesSelection } from "../libraryWorkspace";

const SPECIES_OPTIONS: { value: SpeciesSelection; label: string }[] = [
  { value: "all", label: "All species" },
  { value: "dog", label: "Dogs" },
  { value: "cat", label: "Cats" },
];

function SpeciesIcon({ species }: { species: SpeciesSelection | Species }) {
  if (species === "dog") {
    return <IconDog className="h-4 w-4" aria-hidden="true" />;
  }

  if (species === "cat") {
    return <IconCat className="h-4 w-4" aria-hidden="true" />;
  }

  return <IconPaw className="h-4 w-4" aria-hidden="true" />;
}

interface Props {
  onNavigate: (path: string) => void;
}

export function PetSelector({ onNavigate }: Props) {
  const {
    species,
    identity,
    identities,
    speciesIdentities,
    loadingIdentities,
    identitiesError,
    selectSpecies,
    selectIdentity,
    reloadIdentities,
  } = useLibraryWorkspace();

  const speciesLabel = species === "cat" ? "cats" : species === "dog" ? "dogs" : "pets";

  return (
    <Card>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <h2 className="text-sm font-medium">Species</h2>

          <div className="flex flex-wrap gap-2" role="group" aria-label="Select species">
            {SPECIES_OPTIONS.map((option) => (
              <Button
                key={option.value}
                type="button"
                variant={species === option.value ? "default" : "outline"}
                aria-pressed={species === option.value}
                onClick={() => selectSpecies(option.value)}
              >
                <SpeciesIcon species={option.value} />
                {option.label}
              </Button>
            ))}
          </div>
        </div>

        <div className="space-y-2">
          <h2 className="text-sm font-medium">Pet</h2>

          {identitiesError && (
            <div className="flex flex-wrap items-center gap-3">
              <p className="text-sm text-destructive">{identitiesError}</p>
              <Button variant="outline" onClick={reloadIdentities}>
                <IconRefresh className="h-4 w-4" aria-hidden="true" />
                Retry
              </Button>
            </div>
          )}

          {!identitiesError && loadingIdentities && (
            <p className="text-sm text-muted-foreground">Loading pets…</p>
          )}

          {!identitiesError && !loadingIdentities && (
            <>
              <div className="flex flex-wrap gap-2" role="group" aria-label="Select pet">
                <Button
                  type="button"
                  variant={identity === "" ? "default" : "outline"}
                  aria-pressed={identity === ""}
                  onClick={() => selectIdentity("")}
                >
                  All photos
                </Button>

                {speciesIdentities.map((pet) => (
                  <Button
                    key={pet.id}
                    type="button"
                    variant={identity === pet.name ? "default" : "outline"}
                    aria-pressed={identity === pet.name}
                    onClick={() => selectIdentity(pet.name)}
                  >
                    <SpeciesIcon species={pet.species} />
                    {pet.name}
                  </Button>
                ))}
              </div>

              {speciesIdentities.length === 0 && (
                <div className="flex flex-wrap items-center gap-3">
                  <p className="text-sm text-muted-foreground">
                    {identities.length === 0
                      ? "No dogs or cats configured yet -- add one to browse the library one pet at a time."
                      : `No ${speciesLabel} configured yet -- add one to browse the library one pet at a time.`}
                  </p>
                  <Button onClick={() => onNavigate("/dogs")}>Go to Dogs &amp; Cats</Button>
                </div>
              )}
            </>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
