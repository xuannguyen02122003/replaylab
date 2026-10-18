import { failedRunEvents, makeEvent } from "../test/fixtures";
import { buildRows, findCause } from "./tree";

describe("buildRows", () => {
  it("orders by sequence and computes depth from parents", () => {
    const rows = buildRows([...failedRunEvents].reverse());
    expect(rows.map((r) => r.event.sequence)).toEqual([0, 1, 2, 3, 4, 5]);
    expect(rows.map((r) => r.depth)).toEqual([0, 0, 1, 1, 2, 0]);
    expect(rows.every((r) => !r.orphan)).toBe(true);
  });

  it("marks events whose parent was not received", () => {
    const rows = buildRows([makeEvent({ sequence: 1, parent_event_id: "missing" })]);
    expect(rows[0]).toMatchObject({ depth: 0, orphan: true });
  });
});

describe("findCause", () => {
  it("finds the exception raised below a failed span", () => {
    const processOrder = failedRunEvents[1];
    expect(findCause(processOrder, failedRunEvents)?.error?.type).toBe("OutOfStockError");
  });

  it("returns null for a span the exception did not pass through", () => {
    expect(findCause(failedRunEvents[2], failedRunEvents)).toBeNull();
  });
});
