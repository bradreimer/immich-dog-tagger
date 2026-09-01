import { Card, CardContent } from "@/components/ui/card";
import type { ClusterSort } from "@/types/clusters";
import type { Dog } from "@/types/dogs";

export type LibrarySpeciesFilter = "all" | "dog" | "cat";
export type LibraryReviewedFilter = "all" | "reviewed" | "unreviewed";

const SELECT_CLASS =
  "h-10 rounded-md border border-input bg-background px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2";

interface Props {
  species: LibrarySpeciesFilter;
  onSpeciesChange: (species: LibrarySpeciesFilter) => void;
  identity: string;
  onIdentityChange: (identity: string) => void;
  identities: Dog[];
  reviewedFilter: LibraryReviewedFilter;
  onReviewedFilterChange: (filter: LibraryReviewedFilter) => void;
  capturedAfter: string;
  onCapturedAfterChange: (value: string) => void;
  capturedBefore: string;
  onCapturedBeforeChange: (value: string) => void;
  sort: ClusterSort;
  onSortChange: (sort: ClusterSort) => void;
}

export function LibraryFilters({
  species,
  onSpeciesChange,
  identity,
  onIdentityChange,
  identities,
  reviewedFilter,
  onReviewedFilterChange,
  capturedAfter,
  onCapturedAfterChange,
  capturedBefore,
  onCapturedBeforeChange,
  sort,
  onSortChange,
}: Props) {
  return (
    <Card>
      <CardContent className="flex flex-wrap items-end gap-4">
        <label className="flex flex-col gap-1 text-sm text-muted-foreground">
          Species
          <select
            value={species}
            onChange={(event) =>
              onSpeciesChange(event.target.value as LibrarySpeciesFilter)
            }
            className={SELECT_CLASS}
          >
            <option value="all">All species</option>
            <option value="dog">Dog</option>
            <option value="cat">Cat</option>
          </select>
        </label>

        <label className="flex flex-col gap-1 text-sm text-muted-foreground">
          Pet
          <select
            value={identity}
            onChange={(event) => onIdentityChange(event.target.value)}
            className={SELECT_CLASS}
          >
            <option value="">All pets</option>
            {identities.map((dog) => (
              <option key={dog.id} value={dog.name}>
                {species === "all"
                  ? `${dog.name} (${dog.species === "cat" ? "Cat" : "Dog"})`
                  : dog.name}
              </option>
            ))}
          </select>
        </label>

        <label className="flex flex-col gap-1 text-sm text-muted-foreground">
          Review status
          <select
            value={reviewedFilter}
            onChange={(event) =>
              onReviewedFilterChange(event.target.value as LibraryReviewedFilter)
            }
            className={SELECT_CLASS}
          >
            <option value="all">All</option>
            <option value="reviewed">Reviewed</option>
            <option value="unreviewed">Unreviewed</option>
          </select>
        </label>

        <div className="flex flex-col gap-1 text-sm text-muted-foreground">
          Captured between
          <div className="flex items-center gap-2">
            <input
              type="date"
              value={capturedAfter}
              onChange={(event) => onCapturedAfterChange(event.target.value)}
              aria-label="Captured after"
              className={SELECT_CLASS}
            />
            <span>and</span>
            <input
              type="date"
              value={capturedBefore}
              onChange={(event) => onCapturedBeforeChange(event.target.value)}
              aria-label="Captured before"
              className={SELECT_CLASS}
            />
          </div>
        </div>

        <label className="flex flex-col gap-1 text-sm text-muted-foreground">
          Sort
          <select
            value={sort}
            onChange={(event) => onSortChange(event.target.value as ClusterSort)}
            className={SELECT_CLASS}
          >
            <option value="captured_desc">Newest first</option>
            <option value="captured_asc">Oldest first</option>
            <option value="confidence_desc">Most confident first</option>
            <option value="confidence_asc">Least confident first</option>
          </select>
        </label>
      </CardContent>
    </Card>
  );
}
