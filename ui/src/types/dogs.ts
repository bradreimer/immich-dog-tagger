export type Species = "dog" | "cat";

export interface Dog {
  id: number;
  name: string;
  species: Species;
  active: boolean;
  /** Key thumbnail crop (same pick as Friends in Frame); null when none is eligible. */
  key_crop_id?: number | null;
}

export interface DogMergeResult {
  source: Dog;
  target: Dog;
  classifications_reassigned: number;
  examples_reassigned: number;
  examples_discarded: number;
  occurrences_reassigned: number;
}
