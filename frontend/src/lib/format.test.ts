import { formatDelta, formatDuration, formatTick } from "./format";

describe("format helpers", () => {
  it("formats durations at the right precision", () => {
    expect(formatDuration(null)).toBe("—");
    expect(formatDuration(0.014)).toBe("0.01 ms");
    expect(formatDuration(6.669)).toBe("6.7 ms");
    expect(formatDuration(1520)).toBe("1.52 s");
  });

  it("formats signed deltas", () => {
    expect(formatDelta(58)).toBe("+58.0 ms");
    expect(formatDelta(-17.3)).toBe("−17.3 ms");
  });

  it("formats axis ticks without trailing zeros", () => {
    expect(formatTick(0)).toBe("0 ms");
    expect(formatTick(5)).toBe("5 ms");
    expect(formatTick(0.5)).toBe("0.5 ms");
    expect(formatTick(1500)).toBe("1.5 s");
  });
});
