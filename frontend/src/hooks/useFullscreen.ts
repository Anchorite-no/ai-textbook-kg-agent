/** 浏览器全屏（F11 效果）。使用 document.documentElement 而非某个 div。 */

import { useCallback, useEffect, useState } from "react";

export function useFullscreen() {
  const [isFullscreen, setIsFullscreen] = useState(false);

  useEffect(() => {
    function onChange() {
      setIsFullscreen(!!document.fullscreenElement);
    }
    document.addEventListener("fullscreenchange", onChange);
    return () => document.removeEventListener("fullscreenchange", onChange);
  }, []);

  const enter = useCallback(() => {
    document.documentElement.requestFullscreen().catch((err) => {
      console.warn("Fullscreen request failed:", err);
    });
  }, []);

  const exit = useCallback(() => {
    if (document.fullscreenElement) {
      document.exitFullscreen().catch((err) => {
        console.warn("Exit fullscreen failed:", err);
      });
    }
  }, []);

  const toggle = useCallback(() => {
    if (isFullscreen) exit();
    else enter();
  }, [isFullscreen, enter, exit]);

  return { isFullscreen, enter, exit, toggle };
}
