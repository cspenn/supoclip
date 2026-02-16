/**
 * Tests for utility functions used across the SupoClip frontend.
 *
 * Covers:
 * - cn() class name merging utility (lib/utils.ts)
 * - formatDate() detailed date formatting (lib/date-utils.ts)
 * - formatSimpleDate() simple date formatting (lib/date-utils.ts)
 * - formatDuration() duration formatting (lib/date-utils.ts)
 * - useApiUrl() hook return value (hooks/useApiUrl.ts)
 */

import { cn } from "@/lib/utils";
import { formatDate, formatSimpleDate, formatDuration } from "@/lib/date-utils";

// ---------------------------------------------------------------------------
// cn() — Tailwind class merging utility
// ---------------------------------------------------------------------------
describe("cn() utility", () => {
  it("merges multiple class strings", () => {
    const result = cn("text-red-500", "bg-blue-200");
    expect(result).toContain("text-red-500");
    expect(result).toContain("bg-blue-200");
  });

  it("resolves conflicting Tailwind classes (last wins)", () => {
    // twMerge should keep only the last conflicting utility
    const result = cn("text-red-500", "text-blue-500");
    expect(result).toBe("text-blue-500");
  });

  it("handles conditional classes via clsx", () => {
    const isActive = true;
    const isDisabled = false;
    const result = cn("base-class", isActive && "active", isDisabled && "disabled");
    expect(result).toContain("base-class");
    expect(result).toContain("active");
    expect(result).not.toContain("disabled");
  });

  it("handles undefined and null values gracefully", () => {
    const result = cn("base", undefined, null, "extra");
    expect(result).toContain("base");
    expect(result).toContain("extra");
  });

  it("handles empty string inputs", () => {
    const result = cn("", "valid-class", "");
    expect(result).toBe("valid-class");
  });

  it("returns an empty string when called with no arguments", () => {
    const result = cn();
    expect(result).toBe("");
  });

  it("handles array inputs via clsx", () => {
    const result = cn(["class-a", "class-b"]);
    expect(result).toContain("class-a");
    expect(result).toContain("class-b");
  });

  it("handles object inputs via clsx", () => {
    const result = cn({ "text-lg": true, "text-sm": false, "font-bold": true });
    expect(result).toContain("text-lg");
    expect(result).toContain("font-bold");
    expect(result).not.toContain("text-sm");
  });
});

// ---------------------------------------------------------------------------
// formatDate() — detailed date formatting
// ---------------------------------------------------------------------------
describe("formatDate()", () => {
  it("formats an ISO date string to a detailed format", () => {
    // Use a fixed timezone-safe approach: the function uses Intl.DateTimeFormat("en-US")
    const dateStr = "2024-06-15T14:30:00Z";
    const result = formatDate(dateStr);

    // The result should contain the month abbreviation, day, and year
    expect(result).toContain("Jun");
    expect(result).toContain("15");
    expect(result).toContain("2024");
  });

  it("includes time components (hour and minute)", () => {
    const dateStr = "2024-01-01T09:05:00Z";
    const result = formatDate(dateStr);

    // Should include some time representation
    // The exact format depends on locale, but it should contain digits for time
    expect(result).toMatch(/\d{1,2}:\d{2}/);
  });

  it("handles different months correctly", () => {
    const months = [
      { input: "2024-01-15T00:00:00Z", expected: "Jan" },
      { input: "2024-03-15T00:00:00Z", expected: "Mar" },
      { input: "2024-07-15T00:00:00Z", expected: "Jul" },
      { input: "2024-12-15T00:00:00Z", expected: "Dec" },
    ];

    for (const { input, expected } of months) {
      const result = formatDate(input);
      expect(result).toContain(expected);
    }
  });
});

// ---------------------------------------------------------------------------
// formatSimpleDate() — simple date formatting
// ---------------------------------------------------------------------------
describe("formatSimpleDate()", () => {
  it("formats a date string without time", () => {
    const dateStr = "2024-06-15T14:30:00Z";
    const result = formatSimpleDate(dateStr);

    // Should produce a locale-specific date string without explicit time
    // The result will vary by locale, but should contain the year
    expect(result).toBeTruthy();
    expect(typeof result).toBe("string");
  });

  it("returns a non-empty string for valid input", () => {
    const result = formatSimpleDate("2024-01-01T00:00:00Z");
    expect(result.length).toBeGreaterThan(0);
  });
});

// ---------------------------------------------------------------------------
// formatDuration() — seconds to human-readable duration
// ---------------------------------------------------------------------------
describe("formatDuration()", () => {
  it("formats seconds under a minute", () => {
    expect(formatDuration(0)).toBe("0:00");
    expect(formatDuration(5)).toBe("0:05");
    expect(formatDuration(30)).toBe("0:30");
    expect(formatDuration(59)).toBe("0:59");
  });

  it("formats exact minutes", () => {
    expect(formatDuration(60)).toBe("1:00");
    expect(formatDuration(120)).toBe("2:00");
    expect(formatDuration(300)).toBe("5:00");
  });

  it("formats minutes and seconds", () => {
    expect(formatDuration(83)).toBe("1:23");
    expect(formatDuration(90)).toBe("1:30");
    expect(formatDuration(125)).toBe("2:05");
    expect(formatDuration(599)).toBe("9:59");
  });

  it("formats hours, minutes, and seconds", () => {
    expect(formatDuration(3600)).toBe("1:00:00");
    expect(formatDuration(3661)).toBe("1:01:01");
    expect(formatDuration(7530)).toBe("2:05:30");
  });

  it("pads minutes and seconds in hour format", () => {
    expect(formatDuration(3605)).toBe("1:00:05");
    expect(formatDuration(3660)).toBe("1:01:00");
  });

  it("handles large durations", () => {
    // 10 hours, 5 minutes, 30 seconds
    expect(formatDuration(36330)).toBe("10:05:30");
  });

  it("handles fractional seconds by flooring", () => {
    expect(formatDuration(61.7)).toBe("1:01");
    expect(formatDuration(0.9)).toBe("0:00");
    expect(formatDuration(59.99)).toBe("0:59");
  });
});

// ---------------------------------------------------------------------------
// useApiUrl — returns correct API URL
// ---------------------------------------------------------------------------
describe("useApiUrl()", () => {
  const originalEnv = process.env;

  beforeEach(() => {
    // Reset environment before each test
    jest.resetModules();
    process.env = { ...originalEnv };
  });

  afterAll(() => {
    process.env = originalEnv;
  });

  it("returns the default URL when NEXT_PUBLIC_API_URL is not set", () => {
    delete process.env.NEXT_PUBLIC_API_URL;
    // Re-import to pick up new env
    const { useApiUrl } = require("@/hooks/useApiUrl");
    const result = useApiUrl();
    expect(result).toBe("http://localhost:8008");
  });

  it("returns the custom URL when NEXT_PUBLIC_API_URL is set", () => {
    process.env.NEXT_PUBLIC_API_URL = "https://api.example.com";
    const { useApiUrl } = require("@/hooks/useApiUrl");
    const result = useApiUrl();
    expect(result).toBe("https://api.example.com");
  });
});
