import { useEffect, useRef } from "react";

export function usePolling(load: () => void | Promise<void>, interval: number) {
  const latest = useRef(load);
  latest.current = load;
  useEffect(() => {
    const run = () => { if (!document.hidden) void latest.current(); };
    run();
    const timer = window.setInterval(run, interval);
    document.addEventListener("visibilitychange", run);
    return () => { window.clearInterval(timer); document.removeEventListener("visibilitychange", run); };
  }, [interval]);
}
