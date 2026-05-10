/** matchMedia 监听响应式断点。SSR 兼容写法不需要（vite-only），保持简洁。 */

import { useEffect, useState } from "react";

export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(() =>
    typeof window === "undefined" ? false : window.matchMedia(query).matches
  );

  useEffect(() => {
    const mql = window.matchMedia(query);
    const handler = (e: MediaQueryListEvent) => setMatches(e.matches);
    setMatches(mql.matches);
    mql.addEventListener("change", handler);
    return () => mql.removeEventListener("change", handler);
  }, [query]);

  return matches;
}

/** plan 16 §3.4 的断点常量。 */
export const breakpoints = {
  xs: 768,
  sm: 1024,
  md: 1280,
  lg: 1600
} as const;

export type Breakpoint = "below-xs" | "xs" | "sm" | "md" | "lg";

/** 当前命中哪个断点。`below-xs` = < 768，`xs` = 768-1023，... */
export function useBreakpoint(): Breakpoint {
  const isXs = useMediaQuery(`(min-width: ${breakpoints.xs}px)`);
  const isSm = useMediaQuery(`(min-width: ${breakpoints.sm}px)`);
  const isMd = useMediaQuery(`(min-width: ${breakpoints.md}px)`);
  const isLg = useMediaQuery(`(min-width: ${breakpoints.lg}px)`);
  if (isLg) return "lg";
  if (isMd) return "md";
  if (isSm) return "sm";
  if (isXs) return "xs";
  return "below-xs";
}
