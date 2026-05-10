import type { ReactNode } from "react";
import * as TooltipPrimitive from "@radix-ui/react-tooltip";
import { cn } from "@/utils/cn";

export const TooltipProvider = TooltipPrimitive.Provider;

export interface TooltipProps {
  content: ReactNode;
  children: ReactNode;
  side?: "top" | "right" | "bottom" | "left";
  align?: "start" | "center" | "end";
  delayDuration?: number;
  /** 多行内容、需要展开。默认不允许，强制单行避免视觉过载。 */
  allowMultiline?: boolean;
  className?: string;
  /** asChild 默认 true，把 trigger 直接代理到 children */
  asChild?: boolean;
}

export function Tooltip({
  content,
  children,
  side = "top",
  align = "center",
  delayDuration = 400,
  allowMultiline = false,
  className,
  asChild = true
}: TooltipProps) {
  return (
    <TooltipPrimitive.Root delayDuration={delayDuration}>
      <TooltipPrimitive.Trigger asChild={asChild}>{children}</TooltipPrimitive.Trigger>
      <TooltipPrimitive.Portal>
        <TooltipPrimitive.Content
          side={side}
          align={align}
          sideOffset={6}
          collisionPadding={8}
          className={cn(
            "z-tooltip rounded-control bg-text-strong text-text-inverse text-meta px-2 py-1",
            "shadow-overlay animate-fade-in",
            allowMultiline ? "max-w-xs leading-snug" : "whitespace-nowrap",
            className
          )}
        >
          {content}
          <TooltipPrimitive.Arrow className="fill-text-strong" />
        </TooltipPrimitive.Content>
      </TooltipPrimitive.Portal>
    </TooltipPrimitive.Root>
  );
}
