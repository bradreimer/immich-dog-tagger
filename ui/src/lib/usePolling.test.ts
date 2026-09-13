import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderHook } from "@testing-library/react";

import { usePolling } from "./usePolling";

describe("usePolling", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("does not start a new run before the previous one settles", async () => {
    let resolveFirst: (() => void) | undefined;
    const callback = vi
      .fn()
      .mockImplementationOnce(
        () =>
          new Promise<void>((resolve) => {
            resolveFirst = resolve;
          }),
      )
      .mockResolvedValue(undefined);

    renderHook(() => usePolling(callback, 1000, true));

    await vi.advanceTimersByTimeAsync(1000);
    expect(callback).toHaveBeenCalledTimes(1);

    // A slow first call outlasting several intervals must not stack up
    // additional overlapping calls (issue #319) -- only once it resolves
    // does the next poll get scheduled.
    await vi.advanceTimersByTimeAsync(5000);
    expect(callback).toHaveBeenCalledTimes(1);

    resolveFirst?.();
    await vi.advanceTimersByTimeAsync(0);

    await vi.advanceTimersByTimeAsync(1000);
    expect(callback).toHaveBeenCalledTimes(2);
  });

  it("does not poll while disabled", async () => {
    const callback = vi.fn().mockResolvedValue(undefined);

    renderHook(() => usePolling(callback, 1000, false));

    await vi.advanceTimersByTimeAsync(5000);
    expect(callback).not.toHaveBeenCalled();
  });

  it("stops polling once unmounted", async () => {
    const callback = vi.fn().mockResolvedValue(undefined);

    const { unmount } = renderHook(() => usePolling(callback, 1000, true));

    await vi.advanceTimersByTimeAsync(1000);
    expect(callback).toHaveBeenCalledTimes(1);

    unmount();

    await vi.advanceTimersByTimeAsync(5000);
    expect(callback).toHaveBeenCalledTimes(1);
  });
});
