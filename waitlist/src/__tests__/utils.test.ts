import { describe, it, expect } from "vitest";
import { cn } from "@/lib/utils";

describe("cn utility", () => {
  it("merges class names", () => {
    const result = cn("foo", "bar");
    expect(result).toBe("foo bar");
  });

  it("handles conditional classes via clsx", () => {
    const result = cn("base", false && "hidden", "visible");
    expect(result).toBe("base visible");
  });

  it("returns empty string for no inputs", () => {
    const result = cn();
    expect(result).toBe("");
  });

  it("deduplicates conflicting tailwind classes", () => {
    const result = cn("px-4", "px-6");
    expect(result).toBe("px-6");
  });

  it("merges tailwind classes keeping the last conflicting one", () => {
    const result = cn("text-red-500", "text-blue-500");
    expect(result).toBe("text-blue-500");
  });

  it("handles undefined and null inputs gracefully", () => {
    const result = cn("base", undefined, null, "extra");
    expect(result).toBe("base extra");
  });

  it("handles array inputs", () => {
    const result = cn(["foo", "bar"]);
    expect(result).toBe("foo bar");
  });

  it("handles object inputs for conditional classes", () => {
    const result = cn({ "bg-red-500": true, "bg-blue-500": false });
    expect(result).toBe("bg-red-500");
  });
});
