import { describe, expect, it } from "vitest";

import { formatDate, formatRelativeTime } from "./utils";

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
