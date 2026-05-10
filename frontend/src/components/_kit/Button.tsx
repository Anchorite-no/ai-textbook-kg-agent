import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from "react";
import { Loader2 } from "lucide-react";
import { cn } from "@/utils/cn";

type Variant = "primary" | "secondary" | "ghost" | "destructive";
type Size = "sm" | "md" | "lg";

const variantClass: Record<Variant, string> = {
  primary:
    "bg-brand-500 text-text-inverse hover:bg-brand-600 active:bg-brand-700 disabled:bg-brand-500/50",
  secondary:
    "bg-surface-card text-text-default border border-border-strong hover:bg-surface-input active:bg-surface-muted disabled:opacity-50",
  ghost:
    "bg-transparent text-text-default hover:bg-surface-input active:bg-surface-muted disabled:opacity-50",
  destructive:
    "bg-status-error text-text-inverse hover:brightness-110 active:brightness-95 disabled:opacity-50"
};

const sizeClass: Record<Size, string> = {
  sm: "h-7 px-2.5 text-meta gap-1.5",
  md: "h-8 px-3 text-body gap-2",
  lg: "h-10 px-4 text-body gap-2"
};

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  leftIcon?: ReactNode;
  rightIcon?: ReactNode;
  loading?: boolean;
  fullWidth?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  {
    variant = "primary",
    size = "md",
    leftIcon,
    rightIcon,
    loading = false,
    fullWidth = false,
    disabled,
    className,
    children,
    type = "button",
    ...rest
  },
  ref
) {
  const isDisabled = disabled || loading;
  return (
    <button
      ref={ref}
      type={type}
      disabled={isDisabled}
      className={cn(
        "inline-flex items-center justify-center font-medium rounded-control",
        "transition-[background-color,color,box-shadow,transform] duration-micro ease-standard",
        "select-none whitespace-nowrap",
        variant === "primary" && "hover:-translate-y-px",
        "disabled:cursor-not-allowed",
        variantClass[variant],
        sizeClass[size],
        fullWidth && "w-full",
        className
      )}
      {...rest}
    >
      {loading ? (
        <Loader2 className="size-4 animate-spin" aria-hidden />
      ) : leftIcon ? (
        <span className="shrink-0 inline-flex" aria-hidden>
          {leftIcon}
        </span>
      ) : null}
      {children ? <span className="truncate">{children}</span> : null}
      {!loading && rightIcon ? (
        <span className="shrink-0 inline-flex" aria-hidden>
          {rightIcon}
        </span>
      ) : null}
    </button>
  );
});
