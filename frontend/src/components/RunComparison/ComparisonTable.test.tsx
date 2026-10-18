import { render, screen, within } from "@testing-library/react";

import type { DiffEntry } from "../../types/api";
import { ComparisonTable } from "./ComparisonTable";

const base: Omit<DiffEntry, "key" | "kind" | "operation_name"> = {
  event_type: "span",
  depth: 1,
  base_event_id: "a",
  target_event_id: "b",
  base_sequence: 1,
  target_sequence: 1,
  status_change: null,
  attribute_changes: [],
  error_change: null,
  duration: null,
};

it("shows each kind of difference with its details", () => {
  const entries: DiffEntry[] = [
    {
      ...base,
      key: "/a#0",
      kind: "changed",
      operation_name: "inventory.reserve_stock",
      status_change: { base: "ok", target: "error" },
      attribute_changes: [{ key: "available", change: "changed", base: 10, target: 0 }],
      duration: { base_ms: 2, target_ms: 60, delta_ms: 58, delta_pct: 2900, significant: true },
    },
    { ...base, key: "/b#0", kind: "missing", operation_name: "payment.charge", target_event_id: null, target_sequence: null },
    { ...base, key: "/c#0", kind: "added", operation_name: "inventory.reserve_stock", event_type: "exception", base_event_id: null, base_sequence: null },
  ];
  render(<ComparisonTable entries={entries} />);

  const rows = screen.getAllByRole("row").slice(1);
  expect(rows).toHaveLength(3);
  expect(within(rows[0]).getByText("Changed")).toBeInTheDocument();
  expect(within(rows[0]).getByText("available: 10 → 0")).toBeInTheDocument();
  expect(within(rows[0]).getByText(/\+58\.0 ms/)).toBeInTheDocument();
  expect(within(rows[1]).getByText("Only in base")).toBeInTheDocument();
  expect(within(rows[2]).getByText("exception in inventory.reserve_stock")).toBeInTheDocument();
});
