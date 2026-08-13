export type Species = "dog" | "cat";

export interface Dog {
  id: number;
  name: string;
  species: Species;
  active: boolean;
  active_from: string | null;
  active_until: string | null;
}