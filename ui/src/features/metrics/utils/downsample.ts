/**
 * Reduces `points` to at most `maxPoints` entries for chart display, always
 * keeping the first and last entry so a line chart still spans the full
 * input range. Below `maxPoints`, `points` is returned unchanged so small
 * histories render exactly as before.
 */
export function downsampleForDisplay<T>(points: readonly T[], maxPoints: number): T[] {
  const cap = Math.max(2, maxPoints);

  if (points.length <= cap) {
    return [...points];
  }

  const lastIndex = points.length - 1;
  const sampled: T[] = [];

  for (let i = 0; i < cap; i++) {
    const index = Math.round((i * lastIndex) / (cap - 1));
    sampled.push(points[index]);
  }

  // Rounding can map two adjacent output slots to the same source index
  // when maxPoints is close to points.length -- collapse those so no point
  // is plotted twice.
  return sampled.filter((point, i) => i === 0 || point !== sampled[i - 1]);
}
