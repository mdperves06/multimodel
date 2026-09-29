import { describe, expect, it } from "vitest";
import { duration, formatBytes, formatNumber, safeNext, shortId } from "./format";

describe("safeNext", () => {
  it("allows same-site paths", () => {
    expect(safeNext("/jobs/123")).toBe("/jobs/123");
    expect(safeNext("/gallery?page=2")).toBe("/gallery?page=2");
  });

  it.each([
    "https://evil.example",
    "//evil.example",
    "javascript:alert(1)",
    "evil",
    "",
    null,
  ])("rejects unsafe redirect target %s", (value) => {
    expect(safeNext(value)).toBe("/dashboard");
  });
});

describe("formatters", () => {
  it("formats bytes", () => {
    expect(formatBytes(512)).toBe("512 B");
    expect(formatBytes(2048)).toBe("2.0 KB");
    expect(formatBytes(5 * 1024 * 1024)).toBe("5.0 MB");
  });

  it("never invents numbers for missing values", () => {
    expect(formatNumber(null)).toBe("—");
    expect(formatNumber(undefined)).toBe("—");
    expect(formatNumber(0)).toBe("0");
  });

  it("shortens ids", () => {
    expect(shortId("4e13c0c1-95d2-45a0-b223-f5b5ebd1e19d")).toBe("4e13c0c1");
  });

  it("computes durations", () => {
    expect(duration(null, null)).toBe("—");
    expect(duration("2026-01-01T00:00:00Z", "2026-01-01T00:00:45Z")).toBe("45s");
    expect(duration("2026-01-01T00:00:00Z", "2026-01-01T00:02:05Z")).toBe("2m 5s");
  });
});
