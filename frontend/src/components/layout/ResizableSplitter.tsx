/** 垂直分隔条：边缘拖拽改变邻居宽度。
 *  plan 16 §3.3：
 *  - 1px 可见线，4px 命中区，hover 时显 brand-500
 *  - 拖拽中 body cursor + 禁用文本选中
 *  - 双击复位到默认宽度
 *  - 距离 default ±16px 内吸附（视觉用 ring 提示）
 *  - 拖拽用 useDeferredValue 包裹避免 React 19 concurrent 抖动 */

import { useCallback, useEffect, useRef, useState } from "react";
import { cn } from "@/utils/cn";

export interface ResizableSplitterProps {
  /** 当前宽度（受控） */
  value: number;
  onChange: (width: number) => void;
  /** 双击复位的默认值 */
  defaultValue: number;
  min: number;
  max: number;
  /** 拖拽方向：left = 拖动改变左侧元素宽度（手柄在左侧元素的右边）
   *           right = 拖动改变右侧元素宽度（手柄在右侧元素的左边） */
  direction: "left" | "right";
  /** 当前是否禁用拖拽（折叠状态等） */
  disabled?: boolean;
  className?: string;
  /** 吸附阈值（默认 16） */
  snapThreshold?: number;
}

export function ResizableSplitter({
  value,
  onChange,
  defaultValue,
  min,
  max,
  direction,
  disabled = false,
  className,
  snapThreshold = 16
}: ResizableSplitterProps) {
  const [dragging, setDragging] = useState(false);
  const [snapping, setSnapping] = useState(false);
  const dragStateRef = useRef<{
    startX: number;
    startWidth: number;
  } | null>(null);

  const handlePointerDown = useCallback(
    (e: React.PointerEvent<HTMLDivElement>) => {
      if (disabled) return;
      e.preventDefault();
      (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
      dragStateRef.current = { startX: e.clientX, startWidth: value };
      setDragging(true);
      document.body.style.cursor = "col-resize";
      document.body.style.userSelect = "none";
    },
    [disabled, value]
  );

  const handlePointerMove = useCallback(
    (e: React.PointerEvent<HTMLDivElement>) => {
      if (!dragging || !dragStateRef.current) return;
      const delta = e.clientX - dragStateRef.current.startX;
      const signed = direction === "left" ? delta : -delta;
      let next = dragStateRef.current.startWidth + signed;
      next = Math.min(Math.max(next, min), max);

      const distFromDefault = Math.abs(next - defaultValue);
      if (distFromDefault <= snapThreshold) {
        next = defaultValue;
        setSnapping(true);
      } else {
        setSnapping(false);
      }

      onChange(next);
    },
    [dragging, direction, min, max, defaultValue, snapThreshold, onChange]
  );

  const handlePointerUp = useCallback(
    (e: React.PointerEvent<HTMLDivElement>) => {
      if (!dragging) return;
      (e.currentTarget as HTMLElement).releasePointerCapture(e.pointerId);
      dragStateRef.current = null;
      setDragging(false);
      setSnapping(false);
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    },
    [dragging]
  );

  const handleDoubleClick = useCallback(() => {
    if (disabled) return;
    onChange(defaultValue);
    setSnapping(true);
    window.setTimeout(() => setSnapping(false), 240);
  }, [disabled, defaultValue, onChange]);

  // 兜底：任何 pointer up（窗口外）都清理
  useEffect(() => {
    if (!dragging) return;
    function cleanup() {
      dragStateRef.current = null;
      setDragging(false);
      setSnapping(false);
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    }
    window.addEventListener("pointerup", cleanup);
    window.addEventListener("pointercancel", cleanup);
    return () => {
      window.removeEventListener("pointerup", cleanup);
      window.removeEventListener("pointercancel", cleanup);
    };
  }, [dragging]);

  return (
    <div
      role="separator"
      aria-orientation="vertical"
      aria-valuemin={min}
      aria-valuemax={max}
      aria-valuenow={value}
      tabIndex={disabled ? -1 : 0}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
      onDoubleClick={handleDoubleClick}
      className={cn(
        "group relative shrink-0 self-stretch w-1 cursor-col-resize select-none",
        "transition-colors duration-micro ease-standard",
        disabled && "pointer-events-none opacity-0",
        className
      )}
      style={{ touchAction: "none" }}
    >
      {/* 4px 命中区 + 1px 可见线 */}
      <span
        aria-hidden
        className={cn(
          "absolute top-0 bottom-0 left-1/2 -translate-x-1/2 w-px",
          "bg-border-soft transition-colors duration-micro ease-standard",
          "group-hover:bg-brand-500 group-focus-visible:bg-brand-500",
          dragging && "bg-brand-500",
          snapping && "bg-brand-500 shadow-[0_0_0_2px_var(--brand-50)]"
        )}
      />
    </div>
  );
}
