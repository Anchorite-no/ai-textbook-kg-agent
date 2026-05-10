import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from "react";
import * as TooltipPrimitive from "@radix-ui/react-tooltip";
import { cn } from "@/utils/cn";

type Size = "sm" | "md" | "lg";
type Variant = "ghost" | "secondary";

const sizeClass: Record<Size, string> = {
  sm: "size-7 [&>svg]:size-3.5",
  md: "size-8 [&>svg]:size-4",
  lg: "size-10 [&>svg]:size-5"
};

const variantClass: Record<Variant, string> = {
  ghost: "bg-transparent text-text-muted hover:bg-surface-input hover:text-text-default",
  secondary: "bg-surface-card text-text-default border border-border-strong hover:bg-surface-input"
};

export interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  /** 必填：屏幕阅读器与 tooltip 共用 */
  label: string;
  icon: ReactNode;
  size?: Size;
  variant?: Variant;
  active?: boolean;
  /** 默认 true，所有 icon-only 按钮强制 tooltip（plan 16 §9.4） */
  tooltip?: boolean;
}

export const IconButton = forwardRef<HTMLButtonElement, IconButtonProps>(function IconButton(
  {
    label,
    icon,
    size = "md",
    variant = "ghost",
    active = false,
    tooltip = true,
    className,
    type = "button",
    ...rest
  },
  ref
) {
  const button = (
    <button
      ref={ref}
      type={type}
      aria-label={label}
      aria-pressed={active || undefined}
      className={cn(
        "inline-flex items-center justify-center rounded-control",
        "transition-colors duration-micro ease-standard",
        "disabled:opacity-50 disabled:cursor-not-allowed",
        active && "bg-brand-50 text-brand-700",
        variantClass[variant],
        sizeClass[size],
        className
      )}
      {...rest}
    >
      {icon}
    </button>
  );

  if (!tooltip) return button;

  return (
    <TooltipPrimitive.Root delayDuration={400}>
      <TooltipPrimitive.Trigger asChild>{button}</TooltipPrimitive.Trigger>
      <TooltipPrimitive.Portal>
        <TooltipPrimitive.Content
          sideOffset={6}
          className="z-tooltip rounded-control bg-text-strong px-2 py-1 text-meta text-text-inverse shadow-overlay animate-fade-in"
        >
          {label}
          <TooltipPrimitive.Arrow className="fill-text-strong" />
        </TooltipPrimitive.Content>
      </TooltipPrimitive.Portal>
    </TooltipPrimitive.Root>
  );
});
