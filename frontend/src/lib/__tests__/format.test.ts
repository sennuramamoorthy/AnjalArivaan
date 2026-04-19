import { describe, it, expect } from "vitest";
import { initials, fmtDate, fmtRelative } from "@/lib/format";

describe("format helpers", () => {
  it("initials returns two-letter uppercase for two-word name", () => {
    expect(initials("Meera Krishnan")).toBe("MK");
  });
  it("initials returns single letter for single-word name", () => {
    expect(initials("Lakshmi")).toBe("L");
  });
  it("initials is safe on empty input", () => {
    expect(initials("")).toBe("?");
  });
  it("fmtDate of invalid string returns input", () => {
    expect(fmtDate("not-a-date")).toBe("not-a-date");
  });
  it("fmtDate of null returns em-dash", () => {
    expect(fmtDate(null)).toBe("—");
  });
  it("fmtRelative of null returns em-dash", () => {
    expect(fmtRelative(null)).toBe("—");
  });
});
