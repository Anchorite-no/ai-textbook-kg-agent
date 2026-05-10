import type { ReactNode } from "react";
import { cn } from "@/utils/cn";

type Variant = "neutral" | "brand" | "success" | "warning" | "error" | "info" | "outline";
type Size = "sm" | "md";

const variantClass: Record<Variant, string> = {
  neutral: "bg-surface-input text-text-default",
  brand: "bg-brand-50 text-brand-700",
  success: "bg-status-success/15 text-status-success",
  warning: "bg-status-warning/15 text-status-warning",
  error: "bg-status-error/15 text-status-error",
  info: "bg-status-running/15 text-status-running",
  outline: "bg-transparent text-text-muted border border-border-strong"
};

const sizeClass: Record<Size, string> = {
  sm: "h-5 px-1.5 text-[11px] gap-1",
  md: "h-6 px-2 text-meta gap-1.5"
};

export interface TagProps {
  variant?: Variant;
  size?: Size;
  dot?: boolean;
  dotColor?: string;
  leadingIcon?: ReactNode;
  className?: string;
  children: ReactNode;
}

export function Tag({
  variant = "neutral",
  size = "md",
  dot = false,
  dotColor,
  leadingIcon,
  className,
  children
}: TagProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-pill font-medium leading-none whitespace-nowrap",
        variantClass[variant],
        sizeClass[size],
        className
      )}
    >
      {dot ? (
        <span
          className="inline-block size-1.5 rounded-full shrink-0"
          style={{ backgroundColor: dotColor ?? "currentColor" }}
          aria-hidden
        />
      ) : null}
      {leadingIcon ? (
        <span className="shrink-0 inline-flex [&>svg]:size-3" aria-hidden>
          {leadingIcon}
        </span>
      ) : null}
      <span className="truncate">{children}</span>
    </span>
  );
}
