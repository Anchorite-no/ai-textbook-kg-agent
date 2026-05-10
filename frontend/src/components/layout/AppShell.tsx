/** AppShell：三栏总壳 + splitter 编排。
 *  - 顶栏 56px + workspace 1fr
 *  - 左栏：默认 320，可拖拽 240-480，可折叠到 56 icon rail
 *  - 中栏：flex 1，min-width 480
 *  - 右栏：默认 420，可拖拽 360-560，可整体隐藏
 *  - 拖拽 splitter 持久化到 localStorage（uiStore）
 *  plan 16 §3 + §11 */

import { useEffect } from "react";
import { useUIStore, layoutLimits } from "@/store/uiStore";
import { useGlobalShortcuts } from "@/hooks/useKeyboardShortcuts";
import { TopBar } from "./TopBar";
import { LeftPanel } from "./LeftPanel";
import { CenterCanvas } from "./CenterCanvas";
import { RightPanel } from "./RightPanel";
import { ResizableSplitter } from "./ResizableSplitter";
import { ToastViewport } from "./ToastViewport";

export function AppShell() {
  useGlobalShortcuts();

  const leftWidth = useUIStore((s) => s.leftWidth);
  const rightWidth = useUIStore((s) => s.rightWidth);
  const leftCollapsed = useUIStore((s) => s.leftCollapsed);
  const rightHidden = useUIStore((s) => s.rightHidden);
  const setLeftWidth = useUIStore((s) => s.setLeftWidth);
  const setRightWidth = useUIStore((s) => s.setRightWidth);
  const theme = useUIStore((s) => s.theme);

  // 启动时把 theme 同步到 <html> 上（rehydrate 之外的兜底）
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
  }, [theme]);

  const effectiveLeftWidth = leftCollapsed ? layoutLimits.leftCollapsed : leftWidth;

  return (
    <div className="app-shell">
      <TopBar />
      <main className="workspace overflow-hidden">
        {/* 左栏 */}
        <aside
          className="panel border-r border-border-soft transition-[width] duration-base ease-standard"
          style={{ width: `${effectiveLeftWidth}px` }}
        >
          <LeftPanel />
        </aside>
        <ResizableSplitter
          value={leftWidth}
          onChange={setLeftWidth}
          defaultValue={layoutLimits.leftDefault}
          min={layoutLimits.leftMin}
          max={layoutLimits.leftMax}
          direction="left"
          disabled={leftCollapsed}
        />

        {/* 中栏 */}
        <section
          className="panel flex-1 overflow-hidden"
          style={{ minWidth: "var(--center-min)" }}
        >
          <CenterCanvas />
        </section>

        {/* 右栏 */}
        {!rightHidden ? (
          <>
            <ResizableSplitter
              value={rightWidth}
              onChange={setRightWidth}
              defaultValue={layoutLimits.rightDefault}
              min={layoutLimits.rightMin}
              max={layoutLimits.rightMax}
              direction="right"
            />
            <aside
              className="panel border-l border-border-soft transition-[width] duration-base ease-standard"
              style={{ width: `${rightWidth}px` }}
            >
              <RightPanel />
            </aside>
          </>
        ) : null}
      </main>
      <ToastViewport />
    </div>
  );
}
