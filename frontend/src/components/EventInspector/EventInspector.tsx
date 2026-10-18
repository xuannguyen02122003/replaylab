// Shows the recorded details of one selected event. Nothing here is computed
// or guessed: every value comes from the stored event.

import type { ReactNode } from "react";

import { formatDateTime, formatDuration, formatValue, shortId } from "../../lib/format";
import { findCause } from "../../lib/tree";
import type { TraceEvent } from "../../types/api";

interface Props {
  event: TraceEvent | null;
  events: TraceEvent[];
  onSelect: (event: TraceEvent) => void;
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid grid-cols-[7rem_1fr] gap-2 py-1">
      <dt className="text-muted">{label}</dt>
      <dd className="min-w-0 break-words">{children}</dd>
    </div>
  );
}

function LinkButton({ onClick, children }: { onClick: () => void; children: ReactNode }) {
  return (
    <button type="button" onClick={onClick} className="font-mono text-[13px] text-ok underline decoration-dotted underline-offset-2 hover:decoration-solid">
      {children}
    </button>
  );
}

export function EventInspector({ event, events, onSelect }: Props) {
  if (!event) {
    return (
      <aside aria-label="Event details" className="rounded-lg border border-line bg-panel p-4 text-sm text-muted">
        Select an event in the timeline to see what was recorded.
      </aside>
    );
  }

  const parent = event.parent_event_id ? events.find((e) => e.event_id === event.parent_event_id) : null;
  const children = events.filter((e) => e.parent_event_id === event.event_id);
  const cause = event.event_type === "span" && event.status === "error" && !children.some((c) => c.event_type === "exception")
    ? findCause(event, events)
    : null;
  const attributes = Object.entries(event.attributes);

  return (
    <aside aria-label="Event details" className="rounded-lg border border-line bg-panel text-sm">
      <header className="border-b border-line px-4 py-3">
        <p className="text-xs text-muted">
          {event.event_type} at sequence {event.sequence}
        </p>
        <h2 className="mt-0.5 font-mono text-base font-medium break-all">{event.operation_name}</h2>
      </header>

      <dl className="px-4 py-2">
        <Field label="Status">
          <span className={event.status === "error" ? "font-semibold text-fault" : "font-semibold text-ok"}>{event.status}</span>
        </Field>
        <Field label="Duration">{formatDuration(event.duration_ms)}</Field>
        <Field label="Started">{formatDateTime(event.timestamp)}</Field>
        <Field label="Parent">
          {parent ? (
            <LinkButton onClick={() => onSelect(parent)}>
              #{parent.sequence} {parent.operation_name}
            </LinkButton>
          ) : event.parent_event_id ? (
            <span className="text-warn">Not received ({shortId(event.parent_event_id)})</span>
          ) : (
            <span className="text-muted">None (top level)</span>
          )}
        </Field>
        <Field label="Children">{children.length}</Field>
        <Field label="Event id">
          <span className="font-mono text-xs">{event.event_id}</span>
        </Field>
      </dl>

      {cause && (
        <p className="mx-4 mb-2 rounded-md bg-fault-soft px-3 py-2">
          This span failed because an exception passed through it.{" "}
          <LinkButton onClick={() => onSelect(cause)}>
            See {cause.error?.type} at #{cause.sequence}
          </LinkButton>
        </p>
      )}

      <section className="border-t border-line px-4 py-3">
        <h3 className="font-semibold">Attributes</h3>
        {attributes.length === 0 ? (
          <p className="mt-1 text-muted">No attributes were recorded.</p>
        ) : (
          <table className="mt-2 w-full table-fixed text-[13px]">
            <tbody>
              {attributes.map(([key, value]) => (
                <tr key={key} className="border-t border-line/60 first:border-0">
                  <th scope="row" className="w-2/5 py-1 pr-2 text-left font-mono font-normal text-muted break-all">
                    {key}
                  </th>
                  <td className={`py-1 font-mono break-all ${value === "[REDACTED]" ? "text-warn italic" : ""}`}>{formatValue(value)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {event.error && (
        <section className="border-t border-line px-4 py-3">
          <h3 className="font-semibold text-fault">{event.error.type}</h3>
          <p className="mt-1 break-words">{event.error.message || <span className="text-muted">No message.</span>}</p>
          <h4 className="mt-3 text-xs font-semibold text-muted">Stack trace, innermost call first</h4>
          {event.error.stack.length === 0 ? (
            <p className="mt-1 text-muted">No stack frames were recorded.</p>
          ) : (
            <ol className="mt-1 space-y-1 rounded-md bg-sunken p-2 font-mono text-xs">
              {event.error.stack.map((frame, i) => (
                <li key={`${frame.file}:${frame.line}:${i}`} className={i === 0 ? "text-fault" : ""}>
                  <span className="font-medium">{frame.function}</span>
                  <span className="text-muted">
                    {" "}
                    in {frame.file}:{frame.line}
                  </span>
                </li>
              ))}
            </ol>
          )}
        </section>
      )}
    </aside>
  );
}
