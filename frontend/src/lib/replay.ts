// Recorded-trace playback as a pure state machine (a reducer).
//
// Playback only moves a cursor through the STORED events in sequence order.
// It never runs the original program again.

export interface ReplayState {
  /** null = not replaying (show the whole trace). Otherwise the current position. */
  index: number | null;
  playing: boolean;
  length: number;
}

export type ReplayAction =
  | { type: "play" }
  | { type: "pause" }
  | { type: "stop" }
  | { type: "next" }
  | { type: "prev" }
  | { type: "first" }
  | { type: "last" }
  | { type: "seek"; index: number }
  | { type: "tick" }
  | { type: "reset"; length: number };

export function initialReplay(length: number): ReplayState {
  return { index: null, playing: false, length };
}

const clamp = (value: number, length: number) => Math.max(0, Math.min(value, length - 1));

export function replayReducer(state: ReplayState, action: ReplayAction): ReplayState {
  if (state.length === 0 && action.type !== "reset") return state;
  const last = state.length - 1;

  switch (action.type) {
    case "play": {
      // Pressing play at the end starts again from the beginning.
      const start = state.index === null || state.index >= last ? 0 : state.index;
      return { ...state, index: start, playing: start < last };
    }
    case "pause":
      return { ...state, playing: false };
    case "stop":
      return { ...state, index: null, playing: false };
    case "next":
      return { ...state, index: state.index === null ? 0 : clamp(state.index + 1, state.length), playing: false };
    case "prev":
      return { ...state, index: state.index === null ? 0 : clamp(state.index - 1, state.length), playing: false };
    case "first":
      return { ...state, index: 0, playing: false };
    case "last":
      return { ...state, index: last, playing: false };
    case "seek":
      return { ...state, index: clamp(action.index, state.length), playing: false };
    case "tick": {
      if (!state.playing || state.index === null) return state;
      const index = clamp(state.index + 1, state.length);
      return { ...state, index, playing: index < last };
    }
    case "reset":
      return initialReplay(action.length);
  }
}
