import { describe, expect, it } from "vitest";
import {
  PACKET_FIELDS, VALIDATION_STEPS, categoryLabel, formatPrice, formatWeight, rejectionLabel, tamperHex,
} from "../labels";

describe("labels and display helpers", () => {
  it("formats weights for display only", () => {
    expect(formatWeight(800)).toBe("800 公克");
    expect(formatWeight(12500)).toBe("12.5 公斤");
  });

  it("passes backend money strings through untouched (no frontend maths)", () => {
    expect(formatPrice("19.20")).toBe("NT$ 19.20");
    expect(formatPrice("0.00")).toBe("NT$ 0.00");
  });

  it("falls back to the raw code for unknown values", () => {
    expect(rejectionLabel("SEQUENCE_REPLAY")).toContain("重複");
    expect(rejectionLabel("SOMETHING_NEW")).toBe("SOMETHING_NEW");
    expect(categoryLabel("mystery")).toBe("mystery");
  });

  it("tamperHex flips exactly one bit in the weight field", () => {
    const hex = "AA550001000102006500014000D9847C";
    const out = tamperHex(hex);
    expect(out).toHaveLength(32);
    expect(out).not.toBe(hex);
    const diff = [...hex].map((c, i) => parseInt(c, 16) ^ parseInt(out[i], 16)).filter((x) => x !== 0);
    expect(diff).toEqual([1]);
    expect(tamperHex("AA55")).toBe("AA55");          // leaves malformed input alone
  });

  it("validation steps and packet fields cover the whole protocol", () => {
    expect(VALIDATION_STEPS).toHaveLength(9);
    expect(PACKET_FIELDS[PACKET_FIELDS.length - 1].to).toBe(16);
    expect(PACKET_FIELDS.reduce((n, f) => n + (f.to - f.from), 0)).toBe(16);
  });
});
