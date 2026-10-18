import type { Dispatch, ReactNode } from "react";

import { SPEEDS } from "../../hooks/useReplay";
import type { ReplayAction, ReplayState } from "../../lib/replay";

interface Props {
  state: ReplayState;
  dispatch: Dispatch<ReplayAction>;
  speed: number;
  onSpeedChange: (speed: number) => void;
}

function IconButton({ label, onClick, disabled, children }: { label: string; onClick: () => void; disabled?: boolean; children: ReactNode }) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      onClick={onClick}
      disabled={disabled}
      className="grid size-8 place-items-center rounded-md border border-line bg-panel hover:bg-sunken disabled:opacity-40"
    >
      <svg aria-hidden viewBox="0 0 16 16" className="size-3.5 fill-current">
        {children}
      </svg>
    </button>
  );
}

export function ReplayControls({ state, dispatch, speed, onSpeedChange }: Props) {
  const { index, playing, length } = state;
  const replaying = index !== null;
  const position = index === null ? 0 : index + 1;
  const progress = length === 0 ? 0 : (position / length) * 100;

  return (
    <section aria-label="Replay recorded events" className="rounded-lg border border-line bg-panel px-3 py-2">
      <div className="flex flex-wrap items-center gap-2">
        <IconButton label="First event" onClick={() => dispatch({ type: "first" })} disabled={length === 0}>
          <path d="M3 3h2v10H3zM13 3v10L6 8z" />
        </IconButton>
        <IconButton label="Previous event" onClick={() => dispatch({ type: "prev" })} disabled={length === 0 || index === 0}>
          <path d="M11 3v10L4 8z" />
        </IconButton>
        {playing ? (
          <IconButton label="Pause" onClick={() => dispatch({ type: "pause" })}>
            <path d="M4 3h3v10H4zM9 3h3v10H9z" />
          </IconButton>
        ) : (
          <IconButton label="Play" onClick={() => dispatch({ type: "play" })} disabled={length === 0}>
            <path d="M4 3v10l9-5z" />
          </IconButton>
        )}
        <IconButton label="Next event" onClick={() => dispatch({ type: "next" })} disabled={length === 0 || index === length - 1}>
          <path d="M5 3v10l7-5z" />
        </IconButton>
        <IconButton label="Last event" onClick={() => dispatch({ type: "last" })} disabled={length === 0}>
          <path d="M11 3h2v10h-2zM3 3v10l7-5z" />
        </IconButton>

        <label className="ml-1 flex items-center gap-1 text-sm text-muted">
          Speed
          <select
            value={speed}
            onChange={(e) => onSpeedChange(Number(e.target.value))}
            className="rounded-md border border-line bg-panel px-1 py-0.5 text-ink"
          >
            {SPEEDS.map((s) => (
              <option key={s} value={s}>
                {s}×
              </option>
            ))}
          </select>
        </label>

        <div className="flex min-w-40 flex-1 items-center gap-2">
          <div
            role="progressbar"
            aria-label="Replay progress"
            aria-valuemin={0}
            aria-valuemax={length}
            aria-valuenow={position}
            className="h-1.5 flex-1 overflow-hidden rounded-full bg-sunken"
          >
            <div className="h-full bg-cursor transition-[width] duration-200" style={{ width: `${progress}%` }} />
          </div>
          <span className="font-mono text-xs tabular-nums text-muted">
            {position}/{length}
          </span>
        </div>

        {replaying && (
          <button type="button" onClick={() => dispatch({ type: "stop" })} className="rounded-md px-2 py-1 text-sm text-muted hover:text-ink">
            Exit replay
          </button>
        )}
      </div>
      <p className="mt-1 text-xs text-muted">
        {replaying
          ? "Replaying recorded events in sequence order. The original program is not run again."
          : "Press play to step through the recorded events one by one."}
      </p>
    </section>
  );
}
