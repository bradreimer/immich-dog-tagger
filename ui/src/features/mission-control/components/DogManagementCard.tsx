import { useCallback, useEffect, useState } from "react";

import { IconEdit, IconPlayerPause, IconPlayerPlay, IconPlus } from "@tabler/icons-react";
import {
  activateDog,
  createDog,
  deactivateDog,
  getDogs,
  renameDog,
} from "../../../lib/api";
import type { Dog } from "../../../types/dogs";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export function DogManagementCard() {
  const [dogs, setDogs] = useState<Dog[]>([]);
  const [name, setName] = useState("");
  const [drafts, setDrafts] = useState<Record<number, string>>({});
  const [loading, setLoading] = useState(true);
  const [savingId, setSavingId] = useState<number | "new" | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

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
      const dog = await createDog(name);
      setDogs((current) => [...current, dog]);
      setDrafts((current) => ({ ...current, [dog.id]: dog.name }));
      setName("");
      setMessage(`Created dog “${dog.name}”.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create dog");
    } finally {
      setSavingId(null);
    }
  }, [name]);

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
      setMessage(`Renamed dog to “${updated.name}”.`);
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
      setMessage(updated.active ? `Activated dog “${updated.name}”.` : `Deactivated dog “${updated.name}”.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update dog");
    } finally {
      setSavingId(null);
    }
  }, []);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Dogs</CardTitle>
        <CardDescription>Manage the dog identities used by review and learning.</CardDescription>
      </CardHeader>

      <CardContent className="space-y-4">
        <div className="flex flex-col gap-3 sm:flex-row">
          <input
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="Add a dog name"
            className="h-10 flex-1 rounded-md border border-input bg-background px-3 text-sm outline-none ring-offset-background placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
          />

          <Button onClick={handleCreate} disabled={savingId !== null || !name.trim()}>
            <IconPlus className="h-4 w-4" aria-hidden="true" />
            Add dog
          </Button>
        </div>

        {message && <p className="text-sm text-emerald-600 dark:text-emerald-400">{message}</p>}
        {error && <p className="text-sm text-destructive">{error}</p>}

        {loading ? (
          <p className="text-sm text-muted-foreground">Loading dogs…</p>
        ) : dogs.length === 0 ? (
          <p className="text-sm text-muted-foreground">No dogs configured yet.</p>
        ) : (
          <div className="space-y-3">
            {dogs.map((dog) => (
              <div key={dog.id} className="flex flex-col gap-3 rounded-lg border p-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex-1 space-y-2">
                  <input
                    value={drafts[dog.id] ?? dog.name}
                    onChange={(event) => setDrafts((current) => ({ ...current, [dog.id]: event.target.value }))}
                    className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm outline-none ring-offset-background focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                  />

                  <div className="flex items-center gap-2">
                    <p className="text-xs text-muted-foreground">ID {dog.id}</p>
                    <Badge variant={dog.active ? "default" : "secondary"}>
                      {dog.active ? "Active" : "Inactive"}
                    </Badge>
                  </div>
                </div>

                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    onClick={() => handleRename(dog)}
                    disabled={savingId === dog.id}
                  >
                    <IconEdit className="h-4 w-4" aria-hidden="true" />
                    Rename
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
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}