import { describe, expect, it } from "vitest";
import { act, renderHook } from "@testing-library/react";

import { useSelection } from "./useSelection";

describe("useSelection", () => {
  it("starts with everything selected", () => {
    const { result } = renderHook(() => useSelection([1, 2, 3]));

    expect(result.current.selected).toEqual([1, 2, 3]);
    expect(result.current.selectedCount).toBe(3);
    expect(result.current.allSelected).toBe(true);
    expect(result.current.noneSelected).toBe(false);
  });

  it("toggles one id without disturbing the others", () => {
    const { result } = renderHook(() => useSelection([1, 2, 3]));

    act(() => result.current.toggle(2));

    expect(result.current.selected).toEqual([1, 3]);
    expect(result.current.isSelected(2)).toBe(false);

    act(() => result.current.toggle(2));

    expect(result.current.selected).toEqual([1, 2, 3]);
  });

  it("keeps the selected ids in the order of the source list", () => {
    const { result } = renderHook(() => useSelection([5, 3, 9]));

    act(() => result.current.toggle(3));

    expect(result.current.selected).toEqual([5, 9]);
  });

  it("selects all and none", () => {
    const { result } = renderHook(() => useSelection([1, 2, 3]));

    act(() => result.current.selectNone());

    expect(result.current.selected).toEqual([]);
    expect(result.current.noneSelected).toBe(true);

    act(() => result.current.selectAll());

    expect(result.current.selected).toEqual([1, 2, 3]);
  });

  it("resets when the list of ids changes", () => {
    const { result, rerender } = renderHook(({ ids }) => useSelection(ids), {
      initialProps: { ids: [1, 2, 3] },
    });

    act(() => result.current.selectNone());

    expect(result.current.noneSelected).toBe(true);

    rerender({ ids: [7, 8] });

    expect(result.current.selected).toEqual([7, 8]);
  });

  it("keeps the selection when a re-render yields the same ids", () => {
    const { result, rerender } = renderHook(({ ids }) => useSelection(ids), {
      initialProps: { ids: [1, 2, 3] },
    });

    act(() => result.current.toggle(2));

    // A fresh array with the same contents: a re-fetch must not throw away
    // the owner's deselections.
    rerender({ ids: [1, 2, 3] });

    expect(result.current.selected).toEqual([1, 3]);
  });
});
