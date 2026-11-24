import { useEffect, useState } from "react";

// Fetch `url` now and every `ms` milliseconds. Returns {data, error}. Keeps the last good data on a failed poll.
export default function usePoll(url, ms = 2000) {
  const [state, setState] = useState({ data: null, error: null });
  useEffect(() => {
    let alive = true;
    const tick = () =>
      fetch(url).then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
        .then((data) => alive && setState({ data, error: null }))
        .catch((e) => alive && setState((s) => ({ ...s, error: e.message })));
    tick();
    const id = setInterval(tick, ms);
    return () => { alive = false; clearInterval(id); };
  }, [url, ms]);
  return state;
}
