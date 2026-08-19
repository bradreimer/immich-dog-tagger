export type Species = "dog" | "cat";

export interface Dog {
  id: number;
  name: string;
  species: Species;
  active: boolean;
}
export interface DogMergeResult {
  source: Dog;
  target: Dog;
  classifications_reassigned: number;
  examples_reassigned: number;
  examples_discarded: number;
  occurrences_reassigned: number;
}
