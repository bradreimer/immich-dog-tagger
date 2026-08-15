export type Species = "dog" | "cat";

export interface Dog {
  id: number;
  name: string;
  species: Species;
  active: boolean;
}