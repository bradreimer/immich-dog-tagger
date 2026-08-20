import { useCallback, useEffect, useState } from "react";

import { IconArrowLeft, IconArrowRight, IconX } from "@tabler/icons-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ImmichPhotoLink } from "@/features/review/components/ImmichPhotoLink";
import {
  getSettings,
  getUndetectedAssets,
  tagUndetectedAsset,
  untagUndetectedAsset,
} from "@/lib/api";
import { formatDate } from "@/lib/utils";
import type { Dog } from "@/types/dogs";
import type { UndetectedAsset } from "@/types/undetected";

const PAGE_SIZE = 12;

type TaggedFilter = "untagged" | "tagged" | "all";

interface Props {
  identities: Dog[];
}

/**
 * Photos detection found nothing in (issue #147).
 *
 * These have no crop, so there is no local image to show: the photo is
 * identified by its capture date and a link out to Immich, the same
 * approach the review card takes (#128/#132). Nothing is proxied and no
 * image data leaves the deployment.
 */
export function UndetectedPanel({ identities }: Props) {
  const [items, setItems] = useState<UndetectedAsset[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [filter, setFilter] = useState<TaggedFilter>("untagged");
  const [immichUrl, setImmichUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const [page, settings] = await Promise.all([
        getUndetectedAssets({
          limit: PAGE_SIZE,
          offset,
          tagged: filter === "all" ? undefined : filter === "tagged",
        }),
        // The deep link is a convenience; losing it must not take the
        // panel down.
        getSettings().catch(() => null),
      ]);

      setItems(page.items);
      setTotal(page.total);
      setImmichUrl(settings?.immich_external_url || null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load photos");
    } finally {
      setLoading(false);
    }
  }, [offset, filter]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    setOffset(0);
  }, [filter]);

  const tag = useCallback(
    async (asset: UndetectedAsset, identity: string, species: string) => {
      const result = await tagUndetectedAsset(asset.asset_id, identity, species);

      setItems((current) =>
        current.map((item) =>
          item.asset_id === asset.asset_id
            ? { ...item, identities: result.identities }
            : item,
        ),
      );
    },
    [],
  );

  const untag = useCallback(
    async (asset: UndetectedAsset, identity: string, species: string) => {
      const result = await untagUndetectedAsset(
        asset.asset_id,
        identity,
        species,
      );

      setItems((current) =>
        current.map((item) =>
          item.asset_id === asset.asset_id
            ? { ...item, identities: result.identities }
            : item,
        ),
      );
    },
    [],
  );

  const rangeStart = total === 0 ? 0 : offset + 1;
  const rangeEnd = Math.min(offset + PAGE_SIZE, total);

  return (
    <section className="space-y-4" aria-label="Photos with no detected pet">
      <div className="space-y-1">
        <h2 className="text-xl font-semibold tracking-tight">
          Photos with no detected pet
        </h2>
        <p className="text-sm text-muted-foreground">
          The detector found nothing in these, so they never reached review or
          an album. Tagging one adds it to that pet&rsquo;s album on your next
          sync.
        </p>
      </div>

      <div className="flex gap-2" role="group" aria-label="Filter by tagged state">
        {(["untagged", "tagged", "all"] as const).map((option) => (
          <Button
            key={option}
            type="button"
            variant={filter === option ? "default" : "outline"}
            size="sm"
            onClick={() => setFilter(option)}
          >
            {option === "untagged"
              ? "Not tagged"
              : option === "tagged"
                ? "Tagged"
                : "All"}
          </Button>
        ))}
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {!error && loading && (
        <p className="text-sm text-muted-foreground">Loading photos…</p>
      )}

      {!error && !loading && items.length === 0 && (
        <p className="text-sm text-muted-foreground">
          {filter === "untagged"
            ? "Nothing here — every photo the detector missed has been tagged."
            : "No photos match this filter."}
        </p>
      )}

      {!error && !loading && items.length > 0 && (
        <>
          <div className="space-y-2">
            {items.map((asset) => (
              <Card key={asset.asset_id}>
                <CardContent className="flex flex-wrap items-center gap-3 p-3">
                  <span className="text-sm">
                    Taken {formatDate(asset.captured_at)}
                  </span>

                  <ImmichPhotoLink
                    immichUrl={immichUrl}
                    assetId={asset.immich_asset_id}
                  />

                  <div className="flex flex-wrap items-center gap-2">
                    {asset.identities.map((identity) => {
                      const pet = identities.find((dog) => dog.name === identity);

                      return (
                        <Badge
                          key={identity}
                          variant="default"
                          className="flex items-center gap-1"
                        >
                          {identity}
                          <button
                            type="button"
                            aria-label={`Remove ${identity} from this photo`}
                            onClick={() =>
                              untag(asset, identity, pet?.species ?? "dog")
                            }
                            className="rounded-full outline-none focus-visible:ring-2 focus-visible:ring-ring"
                          >
                            <IconX className="h-3 w-3" aria-hidden="true" />
                          </button>
                        </Badge>
                      );
                    })}
                  </div>

                  <select
                    value=""
                    onChange={(event) => {
                      const pet = identities.find(
                        (dog) => String(dog.id) === event.target.value,
                      );

                      if (pet) {
                        tag(asset, pet.name, pet.species);
                      }
                    }}
                    disabled={identities.length === 0}
                    aria-label={`Add a pet to the photo taken ${formatDate(asset.captured_at)}`}
                    className="ml-auto h-9 rounded-md border border-input bg-background px-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                  >
                    <option value="">
                      {identities.length === 0
                        ? "No pets configured"
                        : "This photo contains…"}
                    </option>
                    {identities
                      .filter((dog) => !asset.identities.includes(dog.name))
                      .map((dog) => (
                        <option key={dog.id} value={dog.id}>
                          {dog.name}
                        </option>
                      ))}
                  </select>
                </CardContent>
              </Card>
            ))}
          </div>

          <div className="flex items-center justify-between text-sm text-muted-foreground">
            <span>
              {rangeStart}-{rangeEnd} of {total}
            </span>

            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setOffset((current) => Math.max(0, current - PAGE_SIZE))}
                disabled={offset === 0}
              >
                <IconArrowLeft className="h-4 w-4" aria-hidden="true" />
                Previous
              </Button>

              <Button
                variant="outline"
                size="sm"
                onClick={() => setOffset((current) => current + PAGE_SIZE)}
                disabled={offset + PAGE_SIZE >= total}
              >
                <IconArrowRight className="h-4 w-4" aria-hidden="true" />
                Next
              </Button>
            </div>
          </div>
        </>
      )}
    </section>
  );
}
