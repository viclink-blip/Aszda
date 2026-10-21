"use client";

import { useCallback, useEffect, useRef, useState } from "react";

interface ApiState<T> {
  data: T | undefined;
  error: unknown;
  loading: boolean;
  /** Load again (for example after a change). Keeps showing old data meanwhile. */
  reload: () => Promise<void>;
  /** Update the cached data locally, e.g. after a successful edit. */
  setData: React.Dispatch<React.SetStateAction<T | undefined>>;
}

/**
 * Load data from the API when the component mounts and whenever `deps` change.
 *
 *   const { data, loading, error } = useApi(() => api.projects.get(id), [id]);
 */
export function useApi<T>(loader: () => Promise<T>, deps: React.DependencyList): ApiState<T> {
  const [data, setData] = useState<T | undefined>(undefined);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  // Always call the latest loader without making it a dependency.
  const loaderRef = useRef(loader);
  useEffect(() => {
    loaderRef.current = loader;
  });
  // Ignore responses that arrive after a newer request started.
  const requestId = useRef(0);

  const run = useCallback(async () => {
    const id = ++requestId.current;
    // Start the request first; state updates happen after an await so they never
    // run synchronously inside the effect below.
    const pending = loaderRef.current();
    await Promise.resolve();
    if (id === requestId.current) setLoading(true);
    try {
      const result = await pending;
      if (id === requestId.current) {
        setData(result);
        setError(null);
      }
    } catch (err) {
      if (id === requestId.current) setError(err);
    } finally {
      if (id === requestId.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    void run();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return { data, error, loading, reload: run, setData };
}
