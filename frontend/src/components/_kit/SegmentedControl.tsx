import type { ReactNode } from "react";
import { cn } from "@/utils/cn";

export interface SegmentedOption<T extends string> {
  value: T;
  label: ReactNode;
}

export interface SegmentedControlProps<T extends string> {
  value: T;
  onChange: (value: T) => void;
  options: ReadonlyArray<SegmentedOption<T>>;
  className?: string;
  size?: "sm" | "md";
  ariaLabel?: string;
}

export function SegmentedControl<T extends string>({
  value,
  onChange,
  options,
  className,
  size = "md",
  ariaLabel
}: SegmentedControlProps<T>) {
  return (
    <div
      role="radiogroup"
      aria-label={ariaLabel}
      className={cn(
        "inline-flex items-center rounded-control bg-surface-input p-0.5",
        "border border-border-soft",
        className
      )}
    >
      {options.map((opt) => {
        const active = value === opt.value;
        return (
          <button
            key={opt.value}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => onChange(opt.value)}
            className={cn(
              "inline-flex items-center justify-center font-medium rounded-control",
              "transition-[background-color,color,box-shadow] duration-micro ease-standard",
              size === "sm" ? "h-6 px-2 text-meta" : "h-7 px-2.5 text-meta",
              active
                ? "bg-surface-card text-text-strong shadow-card"
                : "text-text-muted hover:text-text-default"
            )}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}
