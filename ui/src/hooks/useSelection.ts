import { useCallback, useMemo, useState } from "react";

/**
 * Multi-select over a list of ids, for issue #142.
 *
 * The app's first multi-select, so the shape here is deliberately generic:
 * cluster members today, the flat library grid or a review batch later.
 *
 * Two decisions worth keeping if this gets reused:
 *
 * - **Everything starts selected.** Deselecting the odd photo that does not
 *   belong is the exception path, so the common case stays one click. That
 *   makes the *deselected* ids the state worth storing -- an id nobody has
 *   touched is selected by definition, and a list that grows keeps its new
 *   members selected without a reconciliation pass.
 * - **A changed list resets the selection.** A selection is only meaningful
 *   against the list it was made over, so when the ids change -- a different
 *   pet, a re-fetched cluster set -- the exceptions are dropped rather than
 *   carried across. Adjusting during render rather than in an effect means no
 *   frame ever renders the stale selection.
 */
export interface Selection<T extends string | number> {
  /** The selected ids, in the order of the source list. */
  selected: T[];
  selectedCount: number;
  totalCount: number;
  isSelected: (id: T) => boolean;
  toggle: (id: T) => void;
  selectAll: () => void;
  selectNone: () => void;
  allSelected: boolean;
  noneSelected: boolean;
}

export function useSelection<T extends string | number>(
  ids: readonly T[],
): Selection<T> {
  // Identity of the list, not of the array: a re-fetch that returns the same
  // ids must not throw away the owner's deselections.
  const key = ids.join(",");

  const [state, setState] = useState<{ key: string; deselected: Set<T> }>(() => ({
    key,
    deselected: new Set<T>(),
  }));

  if (state.key !== key) {
    // React's documented "adjust state when a prop changes" pattern: this
    // render is discarded and re-run with the reset state before anything
    // commits, so no frame ever shows the previous list's selection.
    setState({ key, deselected: new Set<T>() });
  }

  const { deselected } = state;

  const isSelected = useCallback((id: T) => !deselected.has(id), [deselected]);

  const toggle = useCallback((id: T) => {
    setState((current) => {
      const next = new Set(current.deselected);

      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }

      return { key: current.key, deselected: next };
    });
  }, []);

  const selectAll = useCallback(() => {
    setState((current) => ({ key: current.key, deselected: new Set<T>() }));
  }, []);

  const selectNone = useCallback(() => {
    setState((current) => ({ key: current.key, deselected: new Set(ids) }));
  }, [ids]);

  const selected = useMemo(
    () => ids.filter((id) => !deselected.has(id)),
    [ids, deselected],
  );

  return {
    selected,
    selectedCount: selected.length,
    totalCount: ids.length,
    isSelected,
    toggle,
    selectAll,
    selectNone,
    allSelected: selected.length === ids.length,
    noneSelected: selected.length === 0,
  };
}
