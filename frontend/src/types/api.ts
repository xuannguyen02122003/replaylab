// TypeScript mirror of the backend response models (backend/app/schemas/api.py).
// If the backend schema changes, change these types too.

export type EventType = "run.started" | "span" | "exception" | "run.finished";
export type EventStatus = "ok" | "error";
export type RunStatus = "ok" | "error" | "unknown";
export type Completeness = "complete" | "incomplete";
export type AttributeValue = string | number | boolean | null;

export interface Issue {
  code: string;
  message: string;
}

export interface Run {
  id: string;
  name: string;
  status: RunStatus;
  completeness: Completeness;
  issues: Issue[];
  started_at: string | null;
  duration_ms: number | null;
  event_count: number;
  error_count: number;
  received_at: string;
  updated_at: string;
}

export interface StackFrame {
  file: string;
  line: number;
  function: string;
}

export interface ErrorInfo {
  type: string;
  message: string;
  stack: StackFrame[];
}

export interface TraceEvent {
  event_id: string;
  run_id: string;
  parent_event_id: string | null;
  sequence: number;
  schema_version: string;
  event_type: EventType;
  operation_name: string;
  timestamp: string;
  duration_ms: number | null;
  status: EventStatus;
  attributes: Record<string, AttributeValue>;
  error: ErrorInfo | null;
}

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface Scenario {
  name: string;
  description: string;
  expected_status: EventStatus;
}

export interface IngestResponse {
  run: Run;
  accepted: number;
  duplicates: number;
}

export type DiffKind = "unchanged" | "changed" | "added" | "missing";

export interface ValueChange {
  base: string | null;
  target: string | null;
}

export interface AttributeChange {
  key: string;
  change: "added" | "removed" | "changed";
  base: AttributeValue;
  target: AttributeValue;
}

export interface DurationChange {
  base_ms: number;
  target_ms: number;
  delta_ms: number;
  delta_pct: number | null;
  significant: boolean;
}

export interface DiffEntry {
  key: string;
  kind: DiffKind;
  event_type: EventType;
  operation_name: string;
  depth: number;
  base_event_id: string | null;
  target_event_id: string | null;
  base_sequence: number | null;
  target_sequence: number | null;
  status_change: ValueChange | null;
  attribute_changes: AttributeChange[];
  error_change: ValueChange | null;
  duration: DurationChange | null;
}

export interface Comparison {
  base: Run;
  target: Run;
  counts: Record<DiffKind, number>;
  warnings: string[];
  entries: DiffEntry[];
}
