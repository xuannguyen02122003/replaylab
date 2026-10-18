import { useCallback, useEffect, useState } from "react";

export type AsyncState<T> =
  | { status: "loading"; data: null; error: null }
  | { status: "success"; data: T; error: null }
  | { status: "error"; data: null; error: Error };

/**
 * Runs an async function and tracks loading / success / error.
 * Re-runs when `deps` change. Results from an outdated call are ignored,
 * so a slow old request can never overwrite a newer one.
 */
export function useAsync<T>(load: () => Promise<T>, deps: unknown[]): AsyncState<T> & { reload: () => void } {
  const [state, setState] = useState<AsyncState<T>>({ status: "loading", data: null, error: null });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let current = true;
    setState({ status: "loading", data: null, error: null });
    load().then(
      (data) => current && setState({ status: "success", data, error: null }),
      (error: unknown) =>
        current && setState({ status: "error", data: null, error: error instanceof Error ? error : new Error(String(error)) }),
    );
    return () => {
      current = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, attempt]);

  const reload = useCallback(() => setAttempt((n) => n + 1), []);
  return { ...state, reload };
}
