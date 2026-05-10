/** 全局键盘快捷键。plan 16 §14。
 *  ⌘\ / Ctrl+\ → 折叠左栏
 *  ⌘B / Ctrl+B → 切换右栏
 *  ⌘K / Ctrl+K → 全局搜索（暂未实现）
 *  ⌘F / Ctrl+F → 图谱搜索（暂未实现）
 *  ESC         → 关闭顶层浮层（暂由各浮层自行处理） */

import { useEffect } from "react";
import { useUIStore } from "@/store/uiStore";

function isMac(): boolean {
  if (typeof navigator === "undefined") return false;
  return /Mac|iPhone|iPad/.test(navigator.platform);
}

export function useGlobalShortcuts() {
  useEffect(() => {
    const mac = isMac();
    function handler(e: KeyboardEvent) {
      const mod = mac ? e.metaKey : e.ctrlKey;
      if (!mod) return;

      // 不拦截在 input / textarea / contenteditable 内的输入
      const target = e.target as HTMLElement | null;
      if (target) {
        const tag = target.tagName;
        if (
          tag === "INPUT" ||
          tag === "TEXTAREA" ||
          target.isContentEditable
        ) {
          // 仅对 ESC 仍处理（跳过其他 mod 组合）
          if (e.key !== "Escape") return;
        }
      }

      switch (e.key) {
        case "\\":
          e.preventDefault();
          useUIStore.getState().toggleLeftCollapsed();
          break;
        case "b":
        case "B":
          e.preventDefault();
          useUIStore.getState().toggleRightHidden();
          break;
        // ⌘K / ⌘F 暂占位，留给后续 GlobalSearch / GraphSearch 实现
        default:
          break;
      }
    }
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);
}
