import { describe, expect, it } from "vitest";

import { formatDate, formatDuration, formatRelativeTime } from "./utils";

describe("formatDate", () => {
  it("formats an ISO timestamp as a long-form date", () => {
    expect(formatDate("2026-01-05T12:00:00Z")).toBe("January 5, 2026");
  });

  it("falls back to a placeholder when the date is unknown", () => {
    expect(formatDate(null)).toBe("Date unknown");
  });
});

describe("formatRelativeTime", () => {
  it("reports seconds under a minute as just now", () => {
    const now = new Date("2026-01-05T12:00:30Z");
    expect(formatRelativeTime(new Date("2026-01-05T12:00:00Z"), now)).toBe("just now");
  });

  it("reports minutes ago", () => {
    const now = new Date("2026-01-05T12:10:00Z");
    expect(formatRelativeTime(new Date("2026-01-05T12:00:00Z"), now)).toBe("10m ago");
  });
});

describe("formatDuration", () => {
  it("formats sub-hour idle time in minutes", () => {
    expect(formatDuration(45 * 60)).toBe("45m");
  });

  it("formats hours with leftover minutes", () => {
    expect(formatDuration(2 * 3600 + 5 * 60)).toBe("2h 5m");
  });

  it("drops leftover minutes on a whole hour", () => {
    expect(formatDuration(3600)).toBe("1h");
  });

  it("formats multi-day idle time", () => {
    expect(formatDuration(3 * 86400 + 4 * 3600)).toBe("3d 4h");
  });

  it("falls back to seconds under a minute", () => {
    expect(formatDuration(30)).toBe("30s");
  });
});
