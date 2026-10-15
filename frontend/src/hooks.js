import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api/client.js";

// Runs an async loader whenever `deps` change; exposes data / loading / error and a reload() function.
export function useAsync(loader, deps) {
  const [state, setState] = useState({ data: null, loading: true, error: null });
  const seq = useRef(0);
  const run = useCallback(() => {
    const id = ++seq.current;
    setState((s) => ({ ...s, loading: true, error: null }));
    loader()
      .then((data) => id === seq.current && setState({ data, loading: false, error: null }))
      .catch((error) => id === seq.current && setState({ data: null, loading: false, error }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  useEffect(() => {
    run();
  }, [run]);
  return { ...state, reload: run };
}

// Loads every employee (100 per page) so pickers and department filters reflect the real database.
export function useAllEmployees() {
  return useAsync(async () => {
    const items = [];
    let page = 1;
    for (;;) {
      const res = await api.listEmployees({ page, page_size: 100 });
      items.push(...res.items);
      if (items.length >= res.total || res.items.length === 0) return items;
      page += 1;
    }
  }, []);
}
