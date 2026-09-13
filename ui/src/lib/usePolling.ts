import { useEffect, useRef } from "react";

/**
 * Re-runs `callback` every `intervalMs` while `enabled`, but only schedules the next
 * run after the current one settles -- unlike `setInterval`, which fires on a fixed
 * clock regardless of whether the previous call is still in flight. Overview and Job
 * Queue both poll GET /jobs + GET /diagnostics this way while jobs are active; with a
 * fixed-clock `setInterval`, a single slow response (e.g. a running pipeline job
 * competing for CPU/DB) let the next tick fire on top of it, and every tick after that
 * piled on more overlapping requests until the DB connection pool was exhausted
 * (issue #319). Waiting for each call to settle keeps at most one in-flight poll per
 * mounted page no matter how slow the backend gets.
 */
export function usePolling(
  callback: () => Promise<unknown>,
  intervalMs: number,
  enabled: boolean,
): void {
  const callbackRef = useRef(callback);
  callbackRef.current = callback;

  useEffect(() => {
    if (!enabled) {
      return;
    }

    let cancelled = false;
    let timer: ReturnType<typeof window.setTimeout>;

    const scheduleNext = () => {
      timer = window.setTimeout(async () => {
        await callbackRef.current();
        if (!cancelled) {
          scheduleNext();
        }
      }, intervalMs);
    };

    scheduleNext();

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [enabled, intervalMs]);
}
