import { useCallback, useEffect, useState } from "react";

import {
  IconAlertTriangle,
  IconArrowMerge,
  IconCat,
  IconChartBar,
  IconDog,
  IconEdit,
  IconPlayerPause,
  IconPlayerPlay,
  IconPlus,
  IconX,
} from "@tabler/icons-react";
import {
  activateDog,
  createDog,
  deactivateDog,
  getDogs,
  mergeDogs,
  renameDog,
} from "../../../lib/api";
import type { Dog, Species } from "../../../types/dogs";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

function speciesLabel(species: Species): string {
  return species === "cat" ? "Cat" : "Dog";
}

interface Props {
  onNavigate: (path: string) => void;
}

export function DogManagementCard({ onNavigate }: Props) {
  const [dogs, setDogs] = useState<Dog[]>([]);
  const [name, setName] = useState("");
  const [species, setSpecies] = useState<Species>("dog");
  const [drafts, setDrafts] = useState<Record<number, string>>({});
  const [loading, setLoading] = useState(true);
  const [savingId, setSavingId] = useState<number | "new" | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Merge is a two-step, bulk, effectively irreversible action, so the row
  // opens a target chooser first and only then asks for confirmation.
  const [mergeSourceId, setMergeSourceId] = useState<number | null>(null);
  const [mergeTargetId, setMergeTargetId] = useState<number | null>(null);
  const [mergeConfirming, setMergeConfirming] = useState(false);

  const loadDogs = useCallback(async (silent = false) => {
    if (!silent) {
      setLoading(true);
    }

    setError(null);

    try {
      const items = await getDogs({ includeInactive: true });
      setDogs(items);
      setDrafts((current) => {
        const next: Record<number, string> = {};

        for (const dog of items) {
          next[dog.id] = current[dog.id] ?? dog.name;
        }

        return next;
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load dogs");
    } finally {
      if (!silent) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    loadDogs();
  }, [loadDogs]);

  const handleCreate = useCallback(async () => {
    setError(null);
    setMessage(null);
    setSavingId("new");

    try {
      const dog = await createDog(name, species);
      setDogs((current) => [...current, dog]);
      setDrafts((current) => ({ ...current, [dog.id]: dog.name }));
      setName("");
      setMessage(`Created ${speciesLabel(dog.species).toLowerCase()} “${dog.name}”.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create dog");
    } finally {
      setSavingId(null);
    }
  }, [name, species]);

  const handleRename = useCallback(async (dog: Dog) => {
    const nextName = drafts[dog.id]?.trim() ?? dog.name;

    if (!nextName || nextName === dog.name) {
      return;
    }

    setError(null);
    setMessage(null);
    setSavingId(dog.id);

    try {
      const updated = await renameDog(dog.id, nextName);
      setDogs((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      setDrafts((current) => ({ ...current, [updated.id]: updated.name }));
      setMessage(`Renamed to “${updated.name}”.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to rename dog");
    } finally {
      setSavingId(null);
    }
  }, [drafts]);

  const toggleActive = useCallback(async (dog: Dog) => {
    setError(null);
    setMessage(null);
    setSavingId(dog.id);

    try {
      const updated = dog.active
        ? await deactivateDog(dog.id)
        : await activateDog(dog.id);

      setDogs((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      setMessage(updated.active ? `Activated “${updated.name}”.` : `Deactivated “${updated.name}”.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update dog");
    } finally {
      setSavingId(null);
    }
  }, []);

  const closeMerge = useCallback(() => {
    setMergeSourceId(null);
    setMergeTargetId(null);
    setMergeConfirming(false);
  }, []);

  const openMerge = useCallback((dog: Dog) => {
    setError(null);
    setMessage(null);
    setMergeSourceId(dog.id);
    setMergeTargetId(null);
    setMergeConfirming(false);
  }, []);

  const handleMerge = useCallback(async () => {
    if (mergeSourceId === null || mergeTargetId === null) {
      return;
    }

    setError(null);
    setMessage(null);
    setSavingId(mergeSourceId);

    try {
      const result = await mergeDogs(mergeSourceId, mergeTargetId);

      setDogs((current) =>
        current.map((item) => {
          if (item.id === result.source.id) {
            return result.source;
          }

          if (item.id === result.target.id) {
            return result.target;
          }

          return item;
        }),
      );

      setMessage(
        `Merged “${result.source.name}” into “${result.target.name}”: ` +
          `${result.classifications_reassigned} photo(s) and ` +
          `${result.examples_reassigned} reference example(s) moved. ` +
          `“${result.source.name}” is now deactivated. Run a sync to update the Immich albums.`,
      );
      closeMerge();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to merge identities");
    } finally {
      setSavingId(null);
    }
  }, [closeMerge, mergeSourceId, mergeTargetId]);

  return (
    <Card>
      <CardContent className="space-y-4">
        <div className="flex flex-col gap-3 sm:flex-row">
          <input
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="Add a name"
            className="h-10 flex-1 rounded-md border border-input bg-background px-3 text-sm outline-none ring-offset-background placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
          />

          <div className="flex gap-2" role="radiogroup" aria-label="Species">
            <Button
              type="button"
              variant={species === "dog" ? "default" : "outline"}
              aria-pressed={species === "dog"}
              onClick={() => setSpecies("dog")}
            >
              <IconDog className="h-4 w-4" aria-hidden="true" />
              Dog
            </Button>
            <Button
              type="button"
              variant={species === "cat" ? "default" : "outline"}
              aria-pressed={species === "cat"}
              onClick={() => setSpecies("cat")}
            >
              <IconCat className="h-4 w-4" aria-hidden="true" />
              Cat
            </Button>
          </div>

          <Button onClick={handleCreate} disabled={savingId !== null || !name.trim()}>
            <IconPlus className="h-4 w-4" aria-hidden="true" />
            Add
          </Button>
        </div>

        {message && <p className="text-sm text-status-good">{message}</p>}
        {error && <p className="text-sm text-destructive">{error}</p>}

        {loading ? (
          <p className="text-sm text-muted-foreground">Loading…</p>
        ) : dogs.length === 0 ? (
          <p className="text-sm text-muted-foreground">No dogs or cats configured yet.</p>
        ) : (
          <div className="space-y-3">
            {dogs.map((dog) => {
              // Identities are unique per species, and a dog and a cat sharing
              // a name are two different animals -- so only same-species
              // identities are offered as merge targets.
              const mergeCandidates = dogs.filter(
                (candidate) => candidate.species === dog.species && candidate.id !== dog.id,
              );
              const mergeTarget = mergeCandidates.find((candidate) => candidate.id === mergeTargetId);

              return (
              <div key={dog.id} className="space-y-3 rounded-lg border p-3">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <div className="flex-1 space-y-2">
                    <input
                      value={drafts[dog.id] ?? dog.name}
                      onChange={(event) => setDrafts((current) => ({ ...current, [dog.id]: event.target.value }))}
                      className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm outline-none ring-offset-background focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                    />

                    <div className="flex items-center gap-2">
                      <p className="text-xs text-muted-foreground">ID {dog.id}</p>
                      <Badge variant="outline">{speciesLabel(dog.species)}</Badge>
                      <Badge variant={dog.active ? "default" : "secondary"}>
                        {dog.active ? "Active" : "Inactive"}
                      </Badge>
                    </div>
                  </div>

                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      onClick={() => onNavigate(`/dogs/${dog.id}/insights`)}
                    >
                      <IconChartBar className="h-4 w-4" aria-hidden="true" />
                      Insights
                    </Button>

                    <Button
                      variant="outline"
                      onClick={() => handleRename(dog)}
                      disabled={savingId === dog.id}
                    >
                      <IconEdit className="h-4 w-4" aria-hidden="true" />
                      Rename
                    </Button>

                    <Button
                      variant="destructive"
                      onClick={() => (mergeSourceId === dog.id ? closeMerge() : openMerge(dog))}
                      disabled={savingId === dog.id || mergeCandidates.length === 0}
                      title={
                        mergeCandidates.length === 0
                          ? `No other ${speciesLabel(dog.species).toLowerCase()} to merge into`
                          : undefined
                      }
                    >
                      <IconArrowMerge className="h-4 w-4" aria-hidden="true" />
                      Merge
                    </Button>

                    <Button
                      variant={dog.active ? "destructive" : "default"}
                      onClick={() => toggleActive(dog)}
                      disabled={savingId === dog.id}
                    >
                      {dog.active ? <IconPlayerPause className="h-4 w-4" aria-hidden="true" /> : <IconPlayerPlay className="h-4 w-4" aria-hidden="true" />}
                      {dog.active ? "Deactivate" : "Activate"}
                    </Button>
                  </div>
                </div>

                {mergeSourceId === dog.id && (
                  <div className="space-y-3 rounded-md border border-destructive/50 bg-destructive/5 p-3">
                    <div className="flex items-start gap-2">
                      <IconAlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-destructive" aria-hidden="true" />
                      <p className="text-sm text-muted-foreground">
                        Merging moves every photo and reference example from “{dog.name}” to another
                        identity and deactivates “{dog.name}”. This cannot be undone.
                      </p>
                    </div>

                    <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
                      <label className="text-sm" htmlFor={`merge-target-${dog.id}`}>
                        Merge into
                      </label>

                      <select
                        id={`merge-target-${dog.id}`}
                        value={mergeTargetId ?? ""}
                        onChange={(event) => {
                          setMergeTargetId(event.target.value ? Number(event.target.value) : null);
                          setMergeConfirming(false);
                        }}
                        className="h-10 flex-1 rounded-md border border-input bg-background px-3 text-sm outline-none ring-offset-background focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                      >
                        <option value="">Select a {speciesLabel(dog.species).toLowerCase()}…</option>
                        {mergeCandidates.map((candidate) => (
                          <option key={candidate.id} value={candidate.id}>
                            {candidate.name}
                            {candidate.active ? "" : " (inactive)"}
                          </option>
                        ))}
                      </select>
                    </div>

                    {mergeConfirming && mergeTarget ? (
                      <div className="space-y-2">
                        <p className="text-sm font-medium text-destructive">
                          Merge “{dog.name}” into “{mergeTarget.name}”?
                        </p>
                        <div className="flex gap-2">
                          <Button
                            variant="destructive"
                            onClick={handleMerge}
                            disabled={savingId === dog.id}
                          >
                            <IconArrowMerge className="h-4 w-4" aria-hidden="true" />
                            {savingId === dog.id ? "Merging…" : `Yes, merge into “${mergeTarget.name}”`}
                          </Button>
                          <Button variant="outline" onClick={closeMerge} disabled={savingId === dog.id}>
                            <IconX className="h-4 w-4" aria-hidden="true" />
                            Cancel
                          </Button>
                        </div>
                      </div>
                    ) : (
                      <div className="flex gap-2">
                        <Button
                          variant="destructive"
                          onClick={() => setMergeConfirming(true)}
                          disabled={mergeTargetId === null || savingId === dog.id}
                        >
                          <IconArrowMerge className="h-4 w-4" aria-hidden="true" />
                          Merge
                        </Button>
                        <Button variant="outline" onClick={closeMerge}>
                          <IconX className="h-4 w-4" aria-hidden="true" />
                          Cancel
                        </Button>
                      </div>
                    )}
                  </div>
                )}
              </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
