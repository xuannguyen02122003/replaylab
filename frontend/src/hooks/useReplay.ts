import { useEffect, useReducer } from "react";

import { initialReplay, replayReducer } from "../lib/replay";

export const SPEEDS = [0.5, 1, 2, 4] as const;
const BASE_INTERVAL_MS = 700;

/** Connects the replay reducer to a timer that advances while playing. */
export function useReplay(length: number, speed: number) {
  const [state, dispatch] = useReducer(replayReducer, length, initialReplay);

  useEffect(() => {
    dispatch({ type: "reset", length });
  }, [length]);

  useEffect(() => {
    if (!state.playing) return;
    const timer = window.setInterval(() => dispatch({ type: "tick" }), BASE_INTERVAL_MS / speed);
    return () => window.clearInterval(timer);
  }, [state.playing, speed]);

  return [state, dispatch] as const;
}
