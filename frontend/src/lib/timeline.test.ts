import { failedRunEvents, makeEvent } from "../test/fixtures";
import { axisTicks, computeLayout } from "./timeline";

describe("computeLayout", () => {
  it("places bars by start time and sizes them by duration", () => {
    const events = [
      makeEvent({ sequence: 1, timestamp: "2026-10-11T11:20:00.000Z", duration_ms: 10 }),
      makeEvent({ sequence: 2, timestamp: "2026-10-11T11:20:00.005Z", duration_ms: 5 }),
    ];
    const { totalMs, bars } = computeLayout(events);
    expect(totalMs).toBe(10);
    expect(bars.get("evt-1")).toEqual({ start: 0, width: 100 });
    expect(bars.get("evt-2")).toEqual({ start: 50, width: 50 });
  });

  it("gives instant events zero width", () => {
    const { bars } = computeLayout(failedRunEvents);
    expect(bars.get("evt-4")?.width).toBe(0);
  });

  it("never draws past the right edge", () => {
    const { bars } = computeLayout(failedRunEvents);
    for (const bar of bars.values()) expect(bar.start + bar.width).toBeLessThanOrEqual(100);
  });

  it("handles an empty run", () => {
    expect(computeLayout([]).totalMs).toBe(0);
  });
});

describe("axisTicks", () => {
  it("uses round steps", () => {
    expect(axisTicks(17)).toEqual([0, 5, 10, 15]);
    expect(axisTicks(320)).toEqual([0, 100, 200, 300]);
  });
});
